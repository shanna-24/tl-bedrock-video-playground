"""Compliance checking service for video content.

This service performs brand safety and compliance analysis using the Bedrock-based
Pegasus video API. Categories and rules are dynamically loaded from S3 configuration files.
"""

import json
import logging
import os
import re
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Callable, Optional

from aws.bedrock_client import BedrockClient
from aws.s3_client import S3Client
from config import Config
from utils.ffmpeg import get_ffmpeg_path

logger = logging.getLogger(__name__)

# S3 prefix for compliance configuration files
COMPLIANCE_CONFIG_S3_PREFIX = "compliance/configuration/"


PROMPT_INTRO_TEMPLATE = """This video is a candidate to be used as paid advertising content to promote the {product_line} product line from {company}, a {category} brand.

{company} requires all promotional advertising video content to exhibit strong brand safety, compliance, and explainability guarantees. Analyse the video in its entirety to determine whether or not the video is suitable to be published as paid advertising content. The analysis must incorporate video content, on-screen text, background audio, and speech."""

IDENTIFIED_ISSUES_TEMPLATE = """**Identified Issues**
IMPORTANT: Only create an issue when there is an actual violation or problem. Do NOT create issues for subcategories that pass - if the video meets the criteria, simply omit that subcategory from the issues list. An empty issues list means the video passed all checks.

For each identified issue (violations only), determine:
1. Timecode: The point in the video where the issue occurs (mm:ss). Include both start and end time.
2. Category: {category_list}.
3. Subcategory: The classification of the issue. {subcategory_guidance}
4. Description: A concise description of what is wrong (not what is correct).
5. Status: MUST be assigned exactly according to these rules:
{issue_status_rules}"""

ANALYSIS_OUTPUT = """**Analysis Output**
Provide the following as output:
- Title: Descriptive title for the video.
- Length: The length of the video (mm:ss).
- Summary: Provide a concise summary of the video (maximum 5 sentences).
- Identified Issues (if any): List all issues with the 5 data points for each as detailed above.

Structure the output in JSON format, suitable for subsequent presentation or processing."""

SUMMARY_ONLY_PROMPT = """Analyse this video and provide a brief summary.

**Analysis Output**
Provide the following as output:
- Title: Descriptive title for the video.
- Length: The length of the video (mm:ss).
- Summary: Provide a concise summary of the video (maximum 5 sentences).

Structure the output in JSON format."""


class ComplianceService:
    """Handles video compliance checking using Pegasus model."""
    
    def __init__(
        self,
        bedrock_client: BedrockClient,
        s3_client: S3Client,
        config: Config,
        search_service: Optional[Any] = None,
        compliance_config_dir: Optional[str] = None
    ):
        """Initialize the ComplianceService.
        
        Args:
            bedrock_client: Client for Bedrock API (Pegasus model)
            s3_client: Client for S3 API
            config: Configuration object
            search_service: Optional SearchService for content relevance pre-check
            compliance_config_dir: Deprecated - configs now loaded from S3
        """
        self.bedrock = bedrock_client
        self.s3 = s3_client
        self.config = config
        self.search_service = search_service
        
        # S3 prefix for compliance configuration
        self.compliance_config_prefix = COMPLIANCE_CONFIG_S3_PREFIX
        
        logger.info(f"ComplianceService initialized with S3 config prefix: s3://{config.s3_bucket_name}/{self.compliance_config_prefix}")
    
    def _load_json_from_s3(self, filename: str) -> Optional[dict]:
        """Load a JSON configuration file from S3.
        
        Args:
            filename: Name of the JSON file (e.g., 'compliance_params.json')
            
        Returns:
            Parsed JSON dict or None if not found
        """
        s3_key = f"{self.compliance_config_prefix}{filename}"
        try:
            response = self.s3.client.get_object(
                Bucket=self.config.s3_bucket_name,
                Key=s3_key
            )
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except self.s3.client.exceptions.NoSuchKey:
            logger.warning(f"Config file not found in S3: {s3_key}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in S3 config {s3_key}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading config from S3 {s3_key}: {e}")
            return None
    
    def _load_params(self) -> dict:
        """Load compliance parameters from S3."""
        params = self._load_json_from_s3("compliance_params.json")
        if params is None:
            raise ValueError(f"Compliance parameters file not found in S3: {self.compliance_config_prefix}compliance_params.json")
        return params
    
    def _load_categories(self) -> list[dict]:
        """Load and sort category configurations from S3.
        
        Automatically discovers all config files with type="analysis" by listing
        files in the compliance config S3 prefix.
        """
        import boto3
        
        categories = []
        
        try:
            # List all files in the compliance config directory
            s3_client = boto3.client("s3", region_name=self.config.aws_region)
            response = s3_client.list_objects_v2(
                Bucket=self.config.s3_bucket_name,
                Prefix=self.compliance_config_prefix
            )
            
            if 'Contents' not in response:
                logger.warning(f"No files found in S3 prefix: {self.compliance_config_prefix}")
                return []
            
            # Check each JSON file for type="analysis"
            for obj in response['Contents']:
                key = obj['Key']
                filename = key.replace(self.compliance_config_prefix, '')
                
                # Skip non-JSON files and params file
                if not filename.endswith('.json') or filename == 'compliance_params.json':
                    continue
                
                # Load and check the config
                category = self._load_json_from_s3(filename)
                if category and category.get("type") == "analysis":
                    categories.append(category)
                    logger.info(f"Loaded analysis category: {filename} (id={category.get('id', 'unknown')}, sequence={category.get('sequence', 999)})")
        
        except Exception as e:
            logger.error(f"Error loading category configs from S3: {e}")
        
        if not categories:
            raise ValueError(f"No analysis category files found in S3 at {self.compliance_config_prefix}")
        
        return sorted(categories, key=lambda x: x.get("sequence", 999))
    
    def _load_precheck_configs(self) -> list[dict]:
        """Load all pre-check configurations from S3.
        
        Automatically discovers all config files with type="pre-check" by listing
        files in the compliance config S3 prefix. Configs are sorted by their 
        'sequence' field (lower sequence runs first).
        
        Returns:
            List of pre-check configurations sorted by sequence, with their filenames
        """
        import boto3
        from botocore.exceptions import ClientError
        
        precheck_configs = []
        
        try:
            # List all files in the compliance config directory
            s3_client = boto3.client("s3", region_name=self.config.aws_region)
            response = s3_client.list_objects_v2(
                Bucket=self.config.s3_bucket_name,
                Prefix=self.compliance_config_prefix
            )
            
            if 'Contents' not in response:
                logger.warning(f"No files found in S3 prefix: {self.compliance_config_prefix}")
                return []
            
            # Check each JSON file for type="pre-check"
            for obj in response['Contents']:
                key = obj['Key']
                filename = key.replace(self.compliance_config_prefix, '')
                
                # Skip non-JSON files and params file
                if not filename.endswith('.json') or filename == 'compliance_params.json':
                    continue
                
                # Load and check the config
                config = self._load_json_from_s3(filename)
                if config and config.get("type") == "pre-check" and config.get("enabled", False):
                    config["_filename"] = filename  # Track which file this came from
                    precheck_configs.append(config)
                    logger.info(f"Loaded pre-check: {filename} (id={config.get('id', 'unknown')}, sequence={config.get('sequence', 999)})")
            
            # Sort by sequence field (lower sequence runs first)
            precheck_configs.sort(key=lambda x: x.get("sequence", 999))
            
            logger.info(f"Loaded {len(precheck_configs)} pre-check configurations")
            
        except Exception as e:
            logger.error(f"Error loading pre-check configs from S3: {e}")
            return []
        
        return precheck_configs
    
    def _load_content_relevance_config(self) -> Optional[dict]:
        """Load content relevance pre-check configuration from S3.
        
        DEPRECATED: Use _load_precheck_configs() instead for generic pre-check loading.
        """
        config = self._load_json_from_s3("content_relevance_check.json")
        if config is None:
            logger.info("Content relevance check config not found in S3, skipping pre-check")
        return config
    
    async def _run_precheck(
        self,
        config: dict,
        index_id: str,
        video_id: str,
        params: dict,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[dict]:
        """Run a generic pre-check using transcription lexical search.
        
        Args:
            config: Pre-check configuration dict with:
                - search_config.search_term: Term(s) to search for
                - search_config.min_results: Minimum matches required
                - search_config.pass_condition: "found" (default) or "not_found"
                  * "found": Pass if min_results found (e.g., content relevance)
                  * "not_found": Pass if min_results NOT found (e.g., profanity check)
            index_id: ID of the index containing the video
            video_id: ID of the video to check
            params: Compliance parameters (contains product_line, company, etc.)
            progress_callback: Optional callback for progress updates
            
        Returns:
            None if check passed, or issue dict if check failed
        """
        check_name = config.get("_filename", "unknown check")
        description = config.get("description", "Pre-check")
        
        if not self.search_service:
            logger.warning(f"Search service not available, skipping {check_name}")
            return None
        
        if progress_callback:
            await progress_callback(f"Running {check_name}...")
        
        search_config = config.get("search_config", {})
        search_term = search_config.get("search_term")
        min_results = search_config.get("min_results", 1)
        pass_condition = search_config.get("pass_condition", "found")  # "found" or "not_found"
        
        if not search_term:
            logger.warning(f"{check_name}: No search_term configured, skipping")
            return None
        
        # Replace placeholders in search term(s)
        if isinstance(search_term, list):
            search_term = [term.format(**params) for term in search_term]
            search_display = f"{search_term[0]} (+{len(search_term)-1} more)" if len(search_term) > 1 else search_term[0]
        else:
            search_term = search_term.format(**params)
            search_display = search_term
        
        logger.info(f"{check_name}: searching for '{search_display}' in video {video_id} (pass_condition={pass_condition})")
        
        try:
            # Perform lexical transcription search
            results = await self.search_service.search_videos(
                index_id=index_id,
                query=search_term,
                video_id=video_id,
                modalities=["transcription"],
                transcription_mode="lexical",
                top_k=min_results,
                generate_screenshots=False
            )
            
            clips = results.clips
            
            # Format search term for logging
            if isinstance(search_term, list):
                search_display = f"{search_term[0]} (+{len(search_term)-1} more)" if len(search_term) > 1 else search_term[0]
            else:
                search_display = search_term
                
            logger.info(f"{check_name}: found {len(clips)} matches for '{search_display}'")
            
            # Determine pass/fail based on pass_condition
            found_enough = len(clips) >= min_results
            
            if pass_condition == "not_found":
                # Pass if NOT found (e.g., profanity check)
                check_passed = not found_enough
            else:
                # Pass if found (e.g., content relevance)
                check_passed = found_enough
            
            if check_passed:
                logger.info(f"{check_name}: PASSED")
                return None
            else:
                logger.info(f"{check_name}: FAILED")
                on_fail = config.get("on_fail", {})
                description = on_fail.get("description", "Pre-check failed")
                description = description.format(**params)
                
                return {
                    "Timecode": "00:00 - end",
                    "Category": on_fail.get("category", "Pre-Check"),
                    "Subcategory": on_fail.get("subcategory", "Failed"),
                    "Status": on_fail.get("status", "BLOCK"),
                    "Description": description
                }
                
        except Exception as e:
            logger.error(f"Error in {check_name}: {e}")
            # On error, continue to next check rather than blocking
            return None
    
    async def _check_content_relevance(
        self,
        index_id: str,
        video_id: str,
        params: dict,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[dict]:
        """Perform content relevance pre-check using transcription lexical search.
        
        DEPRECATED: This method is kept for backward compatibility.
        Use _run_precheck() with _load_precheck_configs() instead.
        
        Args:
            index_id: ID of the index containing the video
            video_id: ID of the video to check
            params: Compliance parameters (contains product_line, company, etc.)
            progress_callback: Optional callback for progress updates
            
        Returns:
            None if content is relevant (passed check), or issue dict if irrelevant
        """
        config = self._load_content_relevance_config()
        
        if not config or not config.get("enabled", False):
            logger.info("Content relevance pre-check is disabled")
            return None
        
        if not self.search_service:
            logger.warning("Search service not available, skipping content relevance pre-check")
            return None
        
        if progress_callback:
            await progress_callback("Checking content relevance...")
        
        search_config = config.get("search_config", {})
        search_term = search_config.get("search_term", "{product_line}")
        min_results = search_config.get("min_results", 1)
        
        # Replace placeholders in search term(s)
        # search_term can be a string or a list of strings
        if isinstance(search_term, list):
            search_term = [term.format(**params) for term in search_term]
            search_display = f"{search_term[0]} (+{len(search_term)-1} more)" if len(search_term) > 1 else search_term[0]
        else:
            search_term = search_term.format(**params)
            search_display = search_term
        
        logger.info(f"Content relevance pre-check: searching for '{search_display}' in video {video_id}")
        
        try:
            # Perform lexical transcription search
            results = await self.search_service.search_videos(
                index_id=index_id,
                query=search_term,
                video_id=video_id,
                modalities=["transcription"],
                transcription_mode="lexical",
                top_k=min_results,
                generate_screenshots=False
            )
            
            clips = results.clips
            
            # Format search term for logging
            if isinstance(search_term, list):
                search_display = f"{search_term[0]} (+{len(search_term)-1} more)" if len(search_term) > 1 else search_term[0]
            else:
                search_display = search_term
                
            logger.info(f"Content relevance pre-check found {len(clips)} matches for '{search_display}'")
            
            if len(clips) >= min_results:
                # Content is relevant, continue to Pegasus analysis
                logger.info("Content relevance pre-check PASSED")
                return None
            else:
                # Content is irrelevant, return issue
                logger.info("Content relevance pre-check FAILED - no product mentions found")
                on_fail = config.get("on_fail", {})
                description = on_fail.get("description", "The video does not mention {product_line}.")
                description = description.format(**params)
                
                return {
                    "Timecode": "00:00 - end",
                    "Category": on_fail.get("category", "Content Relevance"),
                    "Subcategory": on_fail.get("subcategory", "Irrelevant Content"),
                    "Status": on_fail.get("status", "BLOCK"),
                    "Description": description
                }
                
        except Exception as e:
            logger.error(f"Error in content relevance pre-check: {e}")
            # On error, continue to Pegasus analysis rather than blocking
            return None
    
    def _build_category_section(self, category: dict, params: dict) -> str:
        """Build the prompt section for a single category."""
        name = category.get("name", "")
        description = category.get("description", "").format(**params)
        subcategories = category.get("subcategories", [])
        
        section = f"\n\n**{name}**\n{description}"
        
        if subcategories:
            for sub in subcategories:
                sub_name = sub.get("name", "")
                sub_guidance = sub.get("guidance", "").format(**params)
                section += f"\n- {sub_name}: {sub_guidance}"
        
        return section
    
    def build_prompt(self) -> tuple[str, dict]:
        """Build the complete compliance prompt from parameters and categories.
        
        Returns:
            Tuple of (prompt string, params dict)
        """
        params = self._load_params()
        categories = self._load_categories()
        
        # Intro section
        prompt = PROMPT_INTRO_TEMPLATE.format(**params)
        
        # Category sections
        for category in categories:
            prompt += self._build_category_section(category, params)
        
        # Build category references for Identified Issues section
        issue_categories = [cat.get("name", "") for cat in categories]
        category_order = " issues before ".join([f"{cat.lower()}" for cat in issue_categories]) + " issues"
        category_list = " or ".join(issue_categories)
        
        # Build subcategory guidance - explicitly state which categories have subcategories
        categories_with_subs = []
        categories_without_subs = []
        for cat in categories:
            cat_name = cat.get("name", "")
            subcats = cat.get("subcategories", [])
            if subcats:
                subcat_names = [s.get("name", "") for s in subcats]
                categories_with_subs.append(f"{cat_name} (use one of: {', '.join(subcat_names)})")
            else:
                categories_without_subs.append(cat_name)
        
        subcategory_guidance_parts = []
        if categories_with_subs:
            subcategory_guidance_parts.append(f"For categories with defined subcategories: {'; '.join(categories_with_subs)}.")
        if categories_without_subs:
            subcategory_guidance_parts.append(f"Leave Subcategory empty (null or omit) for: {', '.join(categories_without_subs)}.")
        subcategory_guidance = " ".join(subcategory_guidance_parts)
        
        # Build issue-level status rules from subcategory configurations and fallback rules
        issue_status_rules_list = []
        
        for cat in categories:
            cat_name = cat.get("name", "")
            subcats = cat.get("subcategories", [])
            
            # Add rules for subcategories
            for subcat in subcats:
                subcat_name = subcat.get("name", "")
                subcat_status = subcat.get("status", "REVIEW")
                issue_status_rules_list.append(
                    f'   - If Category is "{cat_name}" and Subcategory is "{subcat_name}" then Status is "{subcat_status}"'
                )
            
            # Add fallback rules for categories without subcategories
            if not subcats:
                cat_status = cat.get("status", "REVIEW")
                issue_status_rules_list.append(
                    f'   - If Category is "{cat_name}" then Status is "{cat_status}"'
                )
        
        issue_status_rules = "\n".join(issue_status_rules_list)
        
        # Identified Issues section
        prompt += "\n\n" + IDENTIFIED_ISSUES_TEMPLATE.format(
            category_order=category_order,
            category_list=category_list,
            subcategory_guidance=subcategory_guidance,
            issue_status_rules=issue_status_rules
        )
        
        # Analysis Output section
        prompt += "\n\n" + ANALYSIS_OUTPUT
        
        return prompt, params
    
    def _parse_analysis_response(self, insights: str) -> dict:
        """Parse the analysis response and extract the JSON result."""
        # Try to parse as JSON directly
        try:
            return json.loads(insights)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code block
        if "```json" in insights:
            start = insights.find("```json") + 7
            end = insights.find("```", start)
            if end > start:
                try:
                    return json.loads(insights[start:end].strip())
                except json.JSONDecodeError:
                    pass
        
        # Try to extract JSON from generic code block
        if "```" in insights:
            start = insights.find("```") + 3
            newline = insights.find("\n", start)
            if newline > start:
                start = newline + 1
            end = insights.find("```", start)
            if end > start:
                try:
                    return json.loads(insights[start:end].strip())
                except json.JSONDecodeError:
                    pass
        
        # Try to find JSON object in text
        brace_start = insights.find("{")
        if brace_start >= 0:
            depth = 0
            for i, char in enumerate(insights[brace_start:], brace_start):
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(insights[brace_start:i+1])
                        except json.JSONDecodeError:
                            break
        
        # Return raw response if parsing fails
        return {"raw_response": insights}
    
    def _enforce_issue_statuses(self, result: dict) -> dict:
        """Enforce correct status values on issues and deduplicate by Category/Subcategory.
        
        Args:
            result: Parsed compliance result
            
        Returns:
            Result with corrected issue statuses and deduplicated issues
        """
        issues = result.get("Identified Issues", [])
        if not issues:
            return result
        
        # Load categories to build status lookup
        categories = self._load_categories()
        
        # Build lookup: {category_name: {subcategory_name: status}} and fallback statuses
        status_lookup = {}
        fallback_status = {}
        
        for cat in categories:
            cat_name = cat.get("name", "")
            subcats = cat.get("subcategories", [])
            
            if subcats:
                status_lookup[cat_name] = {
                    sub.get("name", ""): sub.get("status", "REVIEW")
                    for sub in subcats
                }
            else:
                # For categories without subcategories, use category-level status
                fallback_status[cat_name] = cat.get("status", "REVIEW")
        
        # Deduplicate issues by Category/Subcategory (keep first occurrence)
        seen = set()
        deduplicated_issues = []
        for issue in issues:
            cat = issue.get("Category", "")
            subcat = issue.get("Subcategory") or ""
            key = (cat, subcat)
            if key not in seen:
                seen.add(key)
                deduplicated_issues.append(issue)
        
        # Apply correct status to each issue
        for issue in deduplicated_issues:
            cat = issue.get("Category", "")
            subcat = issue.get("Subcategory") or ""
            
            if cat in status_lookup and subcat in status_lookup[cat]:
                issue["Status"] = status_lookup[cat][subcat]
            elif cat in fallback_status:
                issue["Status"] = fallback_status[cat]
        
        result["Identified Issues"] = deduplicated_issues
        return result
    
    def _compute_overall_status(self, result: dict) -> dict:
        """Compute Overall Status from issue statuses.
        
        Rules:
        - If any issue has status BLOCK then overall status is BLOCK
        - Else if any issue has status REVIEW then overall status is REVIEW
        - Else overall status is APPROVE
        
        Args:
            result: Parsed compliance result
            
        Returns:
            Result with corrected Overall Status
        """
        issues = result.get("Identified Issues", [])
        
        has_block = any(
            issue.get("Status", "").upper() == "BLOCK" 
            for issue in issues
        )
        has_review = any(
            issue.get("Status", "").upper() == "REVIEW" 
            for issue in issues
        )
        
        if has_block:
            result["Overall Status"] = "BLOCK"
        elif has_review:
            result["Overall Status"] = "REVIEW"
        elif not issues:
            result["Overall Status"] = "APPROVE"
        # If issues exist but none are BLOCK or REVIEW, keep model's value or default to APPROVE
        elif "Overall Status" not in result:
            result["Overall Status"] = "APPROVE"
        
        return result
    
    async def check_compliance(
        self,
        video_id: str,
        video_s3_uri: str,
        video_filename: str,
        index_id: Optional[str] = None,
        progress_callback: Optional[Callable[[str], None]] = None,
        correlation_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Check video compliance and save results to S3.
        
        Two-stage workflow:
        1. Content relevance pre-check using transcription lexical search
        2. Pegasus video analysis for other compliance categories
        
        Args:
            video_id: ID of the video to check
            video_s3_uri: S3 URI of the video file
            video_filename: Original filename of the video
            index_id: Optional index ID (extracted from S3 URI if not provided)
            progress_callback: Optional callback for progress updates
            correlation_id: Optional correlation ID for tracking
            
        Returns:
            Dict containing compliance results and S3 location
        """
        # Load params early for pre-checks
        params = self._load_params()
        
        # Extract index_id from S3 URI if not provided
        if not index_id:
            index_id = self._extract_index_id_from_s3_uri(video_s3_uri)
            logger.info(f"Extracted index_id '{index_id}' from S3 URI: {video_s3_uri}")
        
        # Stage 1: Run all enabled pre-checks
        precheck_issues = []
        if index_id:
            precheck_configs = self._load_precheck_configs()
            logger.info(f"Running {len(precheck_configs)} pre-checks")
            
            for precheck_config in precheck_configs:
                check_name = precheck_config.get("_filename", "unknown")
                logger.info(f"Running pre-check: {check_name}")
                
                issue = await self._run_precheck(
                    config=precheck_config,
                    index_id=index_id,
                    video_id=video_id,
                    params=params,
                    progress_callback=progress_callback
                )
                
                if issue:
                    precheck_issues.append(issue)
                    logger.info(f"Pre-check {check_name} failed: {issue.get('Description')}")
        
        # If any pre-check failed, only generate summary (skip other compliance checks)
        if precheck_issues:
            if progress_callback:
                await progress_callback("Pre-checks failed - generating summary only...")
            
            prompt = SUMMARY_ONLY_PROMPT
            logger.info(f"Pre-checks failed ({len(precheck_issues)} issues) - using summary-only prompt")
        else:
            if progress_callback:
                await progress_callback("Building compliance prompt...")
            
            # Build the full compliance prompt
            prompt, params = self.build_prompt()
        
        # Log the generated prompt for debugging
        logger.info("=" * 80)
        logger.info("COMPLIANCE PROMPT:")
        logger.info("=" * 80)
        logger.info(prompt)
        logger.info("=" * 80)
        
        if progress_callback:
            await progress_callback("Analyzing video for compliance...")
        
        # Invoke Pegasus model (synchronous call)
        try:
            response = self.bedrock.invoke_pegasus_analysis(
                s3_uri=video_s3_uri,
                prompt=prompt,
                temperature=self.config.compliance.pegasus_temperature,
                max_output_tokens=4096
            )
        except Exception as e:
            logger.error(f"Pegasus invocation failed: {e}")
            raise
        
        if progress_callback:
            await progress_callback("Processing compliance results...")
        
        # Parse the response - invoke_pegasus_analysis returns {"message": str, "finishReason": str}
        insights = response.get("message", "")
        compliance_result = self._parse_analysis_response(insights)
        
        # Handle pre-check failures - add issues and set status
        if precheck_issues:
            # For failed pre-checks, we only have summary - add all the issues
            compliance_result["Identified Issues"] = precheck_issues
            # Set overall status to worst status among pre-check issues
            statuses = [issue.get("Status", "APPROVE") for issue in precheck_issues]
            if "BLOCK" in statuses:
                compliance_result["Overall Status"] = "BLOCK"
            elif "REVIEW" in statuses:
                compliance_result["Overall Status"] = "REVIEW"
            else:
                compliance_result["Overall Status"] = "APPROVE"
        else:
            # Enforce correct status values on issues based on category config
            compliance_result = self._enforce_issue_statuses(compliance_result)
            # Compute Overall Status from issue statuses (don't rely on model)
            compliance_result = self._compute_overall_status(compliance_result)
        
        # Override filename with the correct value (don't rely on model)
        compliance_result["Filename"] = video_filename
        
        # Generate thumbnails for identified issues
        if progress_callback:
            await progress_callback("Generating issue thumbnails...")
        
        issues = compliance_result.get("Identified Issues", [])
        if issues:
            # Get index_id from video_s3_uri (format: s3://bucket/videos/index_id/filename)
            index_id = self._extract_index_id_from_s3_uri(video_s3_uri)
            logger.info(f"Extracted index_id '{index_id}' from S3 URI: {video_s3_uri}")
            if index_id:
                await self._generate_issue_thumbnails(
                    issues=issues,
                    video_id=video_id,
                    index_id=index_id,
                    video_s3_uri=video_s3_uri
                )
            else:
                logger.warning(f"Could not extract index_id from S3 URI: {video_s3_uri}")
        
        # Add metadata (prompt included for UI display but not saved to S3)
        timestamp = datetime.utcnow()
        s3_metadata = {
            "video_id": video_id,
            "video_filename": video_filename,
            "checked_at": timestamp.isoformat(),
            "compliance_params": params
        }
        compliance_result["_metadata"] = s3_metadata.copy()
        
        if progress_callback:
            await progress_callback("Saving compliance results to S3...")
        
        # Save to S3 (without prompt)
        s3_key = f"compliance/reports/{video_id}_{timestamp.strftime('%Y%m%d_%H%M%S')}.json"
        result_json = json.dumps(compliance_result, indent=2)
        
        self.s3.client.put_object(
            Bucket=self.config.s3_bucket_name,
            Key=s3_key,
            Body=result_json.encode('utf-8'),
            ContentType='application/json'
        )
        
        logger.info(f"Compliance results saved to s3://{self.config.s3_bucket_name}/{s3_key}")
        
        # Add prompt to result for UI display (after S3 save)
        compliance_result["_metadata"]["prompt"] = prompt
        
        return {
            "result": compliance_result,
            "s3_key": s3_key,
            "s3_uri": f"s3://{self.config.s3_bucket_name}/{s3_key}"
        }
    
    def _extract_index_id_from_s3_uri(self, s3_uri: str) -> Optional[str]:
        """Extract index_id from S3 URI.
        
        Args:
            s3_uri: S3 URI in format s3://bucket/videos/index_id/filename
            
        Returns:
            index_id or None if not found
        """
        try:
            # Parse s3://bucket/videos/index_id/filename
            parts = s3_uri.replace("s3://", "").split("/")
            if len(parts) >= 3 and parts[1] == "videos":
                return parts[2]
        except Exception as e:
            logger.warning(f"Failed to extract index_id from S3 URI: {e}")
        return None
    
    def _parse_timecode_to_seconds(self, timecode: str) -> Optional[int]:
        """Parse timecode string to seconds.
        
        Args:
            timecode: Timecode string like "00:15" or "00:15 - 00:20"
            
        Returns:
            Start time in seconds or None if parsing fails
        """
        if not timecode:
            return None
        try:
            # Match mm:ss or hh:mm:ss format
            match = re.match(r'(\d+):(\d+)(?::(\d+))?', timecode)
            if match:
                groups = match.groups()
                if groups[2] is not None:  # hh:mm:ss
                    return int(groups[0]) * 3600 + int(groups[1]) * 60 + int(groups[2])
                else:  # mm:ss
                    return int(groups[0]) * 60 + int(groups[1])
        except Exception as e:
            logger.warning(f"Failed to parse timecode '{timecode}': {e}")
        return None
    
    async def _generate_issue_thumbnails(
        self,
        issues: list[dict],
        video_id: str,
        index_id: str,
        video_s3_uri: str
    ) -> None:
        """Generate thumbnails for compliance issues at their timecodes.
        
        Args:
            issues: List of compliance issues
            video_id: ID of the video
            index_id: ID of the index
            video_s3_uri: S3 URI of the video file
        """
        logger.info(f"Generating thumbnails for {len(issues)} compliance issues (video_id={video_id}, index_id={index_id})")
        
        # Collect unique timecodes
        timecodes_to_generate = []
        for issue in issues:
            timecode_str = issue.get("Timecode")
            seconds = self._parse_timecode_to_seconds(timecode_str)
            logger.info(f"Issue timecode '{timecode_str}' parsed to {seconds} seconds")
            if seconds is not None:
                timecodes_to_generate.append((issue, seconds))
        
        if not timecodes_to_generate:
            logger.warning("No valid timecodes found for thumbnail generation")
            return
        
        # Download video once for all thumbnails
        s3_key = video_s3_uri.replace(f"s3://{self.config.s3_bucket_name}/", "")
        logger.info(f"Downloading video from S3 key: {s3_key}")
        
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "video.mp4")
            
            try:
                with open(video_path, 'wb') as f:
                    self.s3.download(s3_key, f)
                logger.info(f"Video downloaded successfully to {video_path}")
            except Exception as e:
                logger.error(f"Failed to download video for thumbnail generation: {e}")
                return
            
            for issue, timecode_seconds in timecodes_to_generate:
                try:
                    thumbnail_key = f"thumbnails/{index_id}/{video_id}/compliance_{timecode_seconds}.jpg"
                    logger.info(f"Processing thumbnail for timecode {timecode_seconds}s, key: {thumbnail_key}")
                    
                    # Check if thumbnail already exists
                    if self.s3.object_exists(thumbnail_key):
                        logger.info(f"Thumbnail already exists at {thumbnail_key}, reusing")
                        # Generate presigned URL
                        thumbnail_url = self.s3.generate_presigned_url(
                            key=thumbnail_key,
                            expiration=3600,
                            http_method="GET"
                        )
                        issue["thumbnail_url"] = thumbnail_url
                        continue
                    
                    # Generate thumbnail using ffmpeg
                    thumbnail_path = os.path.join(tmp_dir, f"thumb_{timecode_seconds}.jpg")
                    
                    result = subprocess.run(
                        [
                            get_ffmpeg_path(),
                            "-ss", str(timecode_seconds),
                            "-i", video_path,
                            "-vframes", "1",
                            "-q:v", "2",
                            "-vf", "scale=320:-1",
                            "-y",
                            thumbnail_path
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode == 0 and os.path.exists(thumbnail_path):
                        # Upload to S3
                        with open(thumbnail_path, "rb") as f:
                            self.s3.client.put_object(
                                Bucket=self.config.s3_bucket_name,
                                Key=thumbnail_key,
                                Body=f.read(),
                                ContentType="image/jpeg"
                            )
                        
                        # Generate presigned URL
                        thumbnail_url = self.s3.generate_presigned_url(
                            key=thumbnail_key,
                            expiration=3600,
                            http_method="GET"
                        )
                        issue["thumbnail_url"] = thumbnail_url
                        logger.info(f"Generated and uploaded compliance thumbnail for {video_id} at {timecode_seconds}s: {thumbnail_url[:100]}...")
                    else:
                        logger.warning(f"Failed to generate thumbnail at {timecode_seconds}s: {result.stderr}")
                        
                except Exception as e:
                    logger.error(f"Error generating thumbnail for issue at {timecode_seconds}s: {e}")
    
    def get_compliance_params(self) -> dict:
        """Get the current compliance parameters with categories.
        
        Returns:
            Dict containing company, category, product_line, and categories list
        """
        params = self._load_params()
        categories = self._load_categories()
        
        # Extract category names for the frontend
        category_names = [cat.get("name", "") for cat in categories]
        
        # Check if content relevance pre-check is enabled
        content_relevance_config = self._load_content_relevance_config()
        if content_relevance_config and content_relevance_config.get("enabled", False):
            # Add content relevance to the beginning of the list
            category_names.insert(0, "Content Relevance")
        
        return {
            **params,
            "categories": category_names
        }
