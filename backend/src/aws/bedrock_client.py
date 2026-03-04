"""Bedrock client wrapper for TwelveLabs models.

This module provides a wrapper around AWS Bedrock Runtime client for invoking
TwelveLabs Marengo and Pegasus models.

Validates: Requirements 7.1
"""

import json
import logging
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError

from config import Config
from exceptions import BedrockError

logger = logging.getLogger(__name__)


class BedrockClient:
    """Wrapper for AWS Bedrock Runtime client.
    
    This class provides methods for invoking TwelveLabs Marengo and Pegasus models
    through Amazon Bedrock. It handles authentication, region configuration, and
    error handling.
    
    Attributes:
        config: Configuration object containing model IDs and AWS settings
        client: boto3 Bedrock Runtime client
    """
    
    def __init__(self, config: Config):
        """Initialize the Bedrock client.
        
        Args:
            config: Configuration object with AWS region and model IDs
        """
        self.config = config
        
        # For Marengo 3.0, we need different model IDs for different operations:
        # - Sync operations (InvokeModel for text): Use inference profile (prefix.model-id)
        # - Async operations (StartAsyncInvoke for video): Use base model (model-id)
        self.marengo_sync_model_id = f"{config.inference_profile_prefix}.{config.marengo_model_id}"
        self.marengo_async_model_id = config.marengo_model_id
        
        # Pegasus also needs inference profile for sync operations
        self.pegasus_model_id = f"{config.inference_profile_prefix}.{config.pegasus_model_id}"
        
        # Claude also needs inference profile for sync operations
        self.claude_model_id = f"{config.inference_profile_prefix}.{config.jockey.claude_model_id}"
        
        # Create Bedrock Runtime client
        self.client = boto3.client(
            "bedrock-runtime",
            region_name=config.aws_region
        )
        
        # Get AWS account ID from STS
        try:
            sts_client = boto3.client("sts", region_name=config.aws_region)
            self.account_id = sts_client.get_caller_identity()["Account"]
            logger.info(f"Retrieved AWS account ID: {self.account_id}")
        except Exception as e:
            logger.warning(f"Failed to get AWS account ID: {e}. BucketOwner will not be set.")
            self.account_id = None
        
        logger.info(
            f"Initialized BedrockClient for region {config.aws_region}"
        )
    
    def invoke_marengo_text_embedding(
        self,
        text: str,
        text_truncate: str = "end"
    ) -> List[float]:
        """Generate text embedding using Marengo model.
        
        This method uses the Marengo Embed model to generate embeddings for text
        queries. This is typically used for search queries.
        
        Args:
            text: Text to embed (max 77 tokens)
            text_truncate: How to truncate text if too long ("end" or "none")
        
        Returns:
            List of floats representing the embedding vector
        
        Raises:
            BedrockError: If the API call fails
        """
        try:
            # Prepare request body for Marengo 3.0 text embedding
            request_body = {
                "inputType": "text",
                "text": {
                    "inputText": text
                }
            }
            
            logger.debug(f"Invoking Marengo for text embedding: {text[:50]}...")
            
            # Invoke model using InvokeModel (synchronous for text)
            response = self.client.invoke_model(
                modelId=self.marengo_sync_model_id,
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response["body"].read())
            
            # Log the full response for debugging
            logger.info(f"Marengo text embedding response: {json.dumps(response_body)}")
            
            # Extract embedding from response
            # Response format for Marengo 3.0: {"data": [{"embedding": [float, ...]}]}
            data = response_body.get("data", [])
            if not data or not isinstance(data, list) or len(data) == 0:
                logger.error(f"Invalid response structure. Full response: {response_body}")
                raise BedrockError(
                    f"Invalid response from Marengo. Response keys: {list(response_body.keys())}"
                )
            
            embedding = data[0].get("embedding", [])
            
            if not embedding:
                logger.error(f"Empty embedding received. Full response: {response_body}")
                raise BedrockError(
                    f"Received empty embedding from Marengo. Data: {data[0]}"
                )
            
            logger.info(f"Generated text embedding with {len(embedding)} dimensions")
            
            return embedding
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            raise BedrockError(
                f"Failed to generate text embedding: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error invoking Marengo: {e}")
            raise BedrockError(
                f"Failed to generate text embedding: {str(e)}"
            ) from e
    def invoke_marengo_multimodal_embedding(
            self,
            text: Optional[str] = None,
            image_bytes: Optional[bytes] = None
        ) -> List[float]:
            """Generate embedding using Marengo model with text and/or image.

            This method supports three modes:
            1. Text-only: Provide only text parameter
            2. Image-only: Provide only image_bytes parameter
            3. Multimodal: Provide both text and image_bytes

            The Marengo model generates embeddings that can be used for similarity
            search across video content using text, visual, or combined queries.

            Args:
                text: Optional text to embed (max 77 tokens)
                image_bytes: Optional image bytes to embed

            Returns:
                List of floats representing the embedding vector

            Raises:
                BedrockError: If the API call fails
                ValueError: If neither text nor image is provided

            Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
            """
            if not text and not image_bytes:
                raise ValueError("At least one of text or image must be provided")

            try:
                # Determine input type based on provided parameters
                if text and image_bytes:
                    input_type = "text_image"
                elif image_bytes:
                    input_type = "image"
                else:
                    input_type = "text"

                # Prepare request body
                request_body: Dict[str, Any] = {
                    "inputType": input_type
                }

                # Handle different input types
                if input_type == "text_image":
                    # Multimodal: combine text and image in text_image property
                    import base64
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    request_body["text_image"] = {
                        "inputText": text,
                        "mediaSource": {
                            "base64String": image_base64
                        }
                    }
                elif input_type == "image":
                    # Image-only
                    import base64
                    image_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    request_body["image"] = {
                        "mediaSource": {
                            "base64String": image_base64
                        }
                    }
                else:
                    # Text-only
                    request_body["text"] = {
                        "inputText": text
                    }

                logger.debug(f"Invoking Marengo for {input_type} embedding")

                # Invoke model using InvokeModel (synchronous)
                response = self.client.invoke_model(
                    modelId=self.marengo_sync_model_id,
                    body=json.dumps(request_body)
                )

                # Parse response
                response_body = json.loads(response["body"].read())

                # Log the full response for debugging
                logger.info(f"Marengo {input_type} embedding response: {json.dumps(response_body)}")

                # Extract embedding from response
                # Response format for Marengo 3.0: {"data": [{"embedding": [float, ...]}]}
                data = response_body.get("data", [])
                if not data or not isinstance(data, list) or len(data) == 0:
                    logger.error(f"Invalid response structure. Full response: {response_body}")
                    raise BedrockError(
                        f"Invalid response from Marengo. Response keys: {list(response_body.keys())}"
                    )

                embedding = data[0].get("embedding", [])

                if not embedding:
                    logger.error(f"Empty embedding received. Full response: {response_body}")
                    raise BedrockError(
                        f"Received empty embedding from Marengo. Data: {data[0]}"
                    )

                logger.info(f"Generated {input_type} embedding with {len(embedding)} dimensions")

                return embedding

            except ClientError as e:
                error_code = e.response.get("Error", {}).get("Code", "Unknown")
                error_message = e.response.get("Error", {}).get("Message", str(e))
                logger.error(f"Bedrock API error ({error_code}): {error_message}")
                raise BedrockError(
                    f"Failed to generate {input_type} embedding: {error_message}"
                ) from e
            except ValueError:
                # Re-raise ValueError without wrapping
                raise
            except Exception as e:
                logger.error(f"Unexpected error invoking Marengo: {e}")
                raise BedrockError(
                    f"Failed to generate embedding: {str(e)}"
                ) from e



    
    def start_marengo_video_embedding(
        self,
        s3_uri: str,
        bucket_owner: Optional[str] = None,
        embedding_options: Optional[List[str]] = None,
        start_sec: float = 0.0,
        length_sec: Optional[float] = None,
        use_fixed_length_sec: Optional[float] = None,
        min_clip_sec: int = 4
    ) -> str:
        """Start asynchronous video embedding generation using Marengo model.
        
        This method starts an asynchronous job to generate embeddings for a video
        stored in S3. The embeddings are used for video search and indexing.
        
        Args:
            s3_uri: S3 URI of the video (e.g., s3://bucket/key)
            bucket_owner: AWS account ID of the bucket owner (optional)
            embedding_options: Types of embeddings to generate
                              (visual, audio, transcription)
            start_sec: Start time in seconds (default: 0)
            length_sec: Length to process in seconds (default: full video)
            use_fixed_length_sec: Fixed duration for each clip (2-10 seconds)
            min_clip_sec: Minimum clip duration (1-5 seconds, default: 4)
        
        Returns:
            Invocation ARN for tracking the async job
        
        Raises:
            BedrockError: If the API call fails
        """
        try:
            # Default embedding options if not specified (Marengo 3.0 format)
            if embedding_options is None:
                embedding_options = ["visual", "audio", "transcription"]
            
            # Build mediaSource object
            media_source: Dict[str, Any] = {
                "s3Location": {
                    "uri": s3_uri
                }
            }
            
            # Add bucket owner - use provided value or account ID from STS
            if bucket_owner:
                media_source["s3Location"]["bucketOwner"] = bucket_owner
            elif self.account_id:
                media_source["s3Location"]["bucketOwner"] = self.account_id
            else:
                raise BedrockError(
                    "bucketOwner is required but AWS account ID could not be determined. "
                    "Please provide bucket_owner parameter or ensure AWS credentials are configured."
                )
            
            # Build video object
            video_config: Dict[str, Any] = {
                "mediaSource": media_source,
                "embeddingOption": embedding_options
            }
            
            # Add segmentation configuration
            if use_fixed_length_sec is not None:
                # Fixed segmentation
                video_config["segmentation"] = {
                    "method": "fixed",
                    "fixed": {
                        "durationSec": use_fixed_length_sec
                    }
                }
            else:
                # Dynamic segmentation (default)
                video_config["segmentation"] = {
                    "method": "dynamic",
                    "dynamic": {
                        "minDurationSec": min_clip_sec
                    }
                }
            
            # Add optional time range
            if start_sec > 0:
                video_config["startSec"] = start_sec
            
            if length_sec is not None:
                video_config["endSec"] = start_sec + length_sec
            
            # Prepare request body for Marengo 3.0 video embedding
            request_body: Dict[str, Any] = {
                "inputType": "video",
                "video": video_config
            }
            
            logger.debug(f"Starting async Marengo embedding for video: {s3_uri}")
            logger.debug(f"Request body: {json.dumps(request_body, indent=2)}")
            
            # Start async invocation
            response = self.client.start_async_invoke(
                modelId=self.marengo_async_model_id,
                modelInput=request_body,
                outputDataConfig={
                    "s3OutputDataConfig": {
                        "s3Uri": f"s3://{self.config.s3_bucket_name}/embeddings/"
                    }
                }
            )
            
            invocation_arn = response.get("invocationArn", "")
            
            logger.info(f"Started async video embedding job: {invocation_arn}")
            
            return invocation_arn
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            raise BedrockError(
                f"Failed to start video embedding: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error starting Marengo async job: {e}")
            raise BedrockError(
                f"Failed to start video embedding: {str(e)}"
            ) from e
    
    def invoke_pegasus_analysis(
        self,
        s3_uri: str,
        prompt: str,
        bucket_owner: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze video using Pegasus model.
        
        This method uses the Pegasus model to analyze video content and generate
        textual descriptions, insights, or answers to questions about the video.
        
        Args:
            s3_uri: S3 URI of the video (e.g., s3://bucket/key)
            prompt: Analysis prompt (max 2000 tokens)
            bucket_owner: AWS account ID of the bucket owner (optional)
            temperature: Temperature for randomness (0-1, default: 0.2)
            max_output_tokens: Maximum tokens to generate (max: 4096)
            response_format: Optional structured output format specification
        
        Returns:
            Dictionary containing:
                - message: Analysis text from the model
                - finishReason: Why the output ended ("stop" or "length")
        
        Raises:
            BedrockError: If the API call fails
        """
        try:
            # Prepare request body for Pegasus analysis
            request_body: Dict[str, Any] = {
                "inputPrompt": prompt,
                "mediaSource": {
                    "s3Location": {
                        "uri": s3_uri
                    }
                },
                "temperature": temperature
            }
            
            # Add bucket owner - required for Pegasus
            if bucket_owner:
                request_body["mediaSource"]["s3Location"]["bucketOwner"] = bucket_owner
            elif self.account_id:
                request_body["mediaSource"]["s3Location"]["bucketOwner"] = self.account_id
            else:
                raise BedrockError(
                    "bucketOwner is required but AWS account ID could not be determined. "
                    "Please provide bucket_owner parameter or ensure AWS credentials are configured."
                )
            
            # Add optional max tokens
            if max_output_tokens is not None:
                request_body["maxOutputTokens"] = max_output_tokens
            
            # Add optional response format
            if response_format is not None:
                request_body["responseFormat"] = response_format
            
            logger.debug(f"Invoking Pegasus for video analysis: {s3_uri}")
            logger.debug(f"Prompt: {prompt[:100]}...")
            
            # Invoke model
            response = self.client.invoke_model(
                modelId=self.pegasus_model_id,
                body=json.dumps(request_body)
            )
            
            # Parse response
            response_body = json.loads(response["body"].read())
            
            # Extract message and finish reason
            result = {
                "message": response_body.get("message", ""),
                "finishReason": response_body.get("finishReason", "unknown")
            }
            
            logger.info(
                f"Pegasus analysis completed (finish reason: {result['finishReason']})"
            )
            
            return result
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            raise BedrockError(
                f"Failed to analyze video: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error invoking Pegasus: {e}")
            raise BedrockError(
                f"Failed to analyze video: {str(e)}"
            ) from e
    
    def invoke_pegasus_analysis_streaming(
        self,
        s3_uri: str,
        prompt: str,
        bucket_owner: Optional[str] = None,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None
    ):
        """Analyze video using Pegasus model with streaming response.
        
        This method uses the Pegasus model with streaming to get real-time
        analysis results as they are generated.
        
        Args:
            s3_uri: S3 URI of the video (e.g., s3://bucket/key)
            prompt: Analysis prompt (max 2000 tokens)
            bucket_owner: AWS account ID of the bucket owner (optional)
            temperature: Temperature for randomness (0-1, default: 0.2)
            max_output_tokens: Maximum tokens to generate (max: 4096)
        
        Yields:
            Chunks of analysis text as they are generated
        
        Raises:
            BedrockError: If the API call fails
        """
        try:
            # Prepare request body
            request_body: Dict[str, Any] = {
                "inputPrompt": prompt,
                "mediaSource": {
                    "s3Location": {
                        "uri": s3_uri
                    }
                },
                "temperature": temperature
            }
            
            # Add bucket owner - required for Pegasus
            if bucket_owner:
                request_body["mediaSource"]["s3Location"]["bucketOwner"] = bucket_owner
            elif self.account_id:
                request_body["mediaSource"]["s3Location"]["bucketOwner"] = self.account_id
            else:
                raise BedrockError(
                    "bucketOwner is required but AWS account ID could not be determined. "
                    "Please provide bucket_owner parameter or ensure AWS credentials are configured."
                )
            
            if max_output_tokens is not None:
                request_body["maxOutputTokens"] = max_output_tokens
            
            logger.debug(f"Invoking Pegasus with streaming for: {s3_uri}")
            
            # Invoke model with streaming
            response = self.client.invoke_model_with_response_stream(
                modelId=self.pegasus_model_id,
                body=json.dumps(request_body)
            )
            
            # Stream the response
            stream = response.get("body")
            if stream:
                for event in stream:
                    chunk = event.get("chunk")
                    if chunk:
                        chunk_data = json.loads(chunk.get("bytes").decode())
                        if "message" in chunk_data:
                            yield chunk_data["message"]
            
            logger.info("Pegasus streaming analysis completed")
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            raise BedrockError(
                f"Failed to analyze video with streaming: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error in streaming Pegasus: {e}")
            raise BedrockError(
                f"Failed to analyze video with streaming: {str(e)}"
            ) from e
    
    def get_async_invocation_status(self, invocation_arn: str) -> Dict[str, Any]:
        """Get the status of an asynchronous invocation.
        
        Args:
            invocation_arn: ARN of the async invocation
        
        Returns:
            Dictionary containing status information:
                - status: Current status (InProgress, Completed, Failed)
                - outputDataConfig: S3 location of results (if completed)
                - failureMessage: Error message (if failed)
        
        Raises:
            BedrockError: If the API call fails
        """
        try:
            response = self.client.get_async_invoke(
                invocationArn=invocation_arn
            )
            
            status_info = {
                "status": response.get("status", "Unknown"),
                "outputDataConfig": response.get("outputDataConfig"),
                "failureMessage": response.get("failureMessage")
            }
            
            logger.debug(f"Async invocation status: {status_info['status']}")
            
            return status_info
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            raise BedrockError(
                f"Failed to get async invocation status: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error getting async status: {e}")
            raise BedrockError(
                f"Failed to get async invocation status: {str(e)}"
            ) from e
    
    def stop_model_invocation_job(self, invocation_arn: str) -> None:
        """Stop a running model invocation job.
        
        Stops a batch inference job. You're only charged for tokens that were
        already processed. The job can only be stopped if its status is InProgress.
        
        Args:
            invocation_arn: ARN of the async invocation to stop
        
        Raises:
            BedrockError: If the API call fails
        """
        try:
            # Extract job identifier from ARN
            # ARN format: arn:aws:bedrock:region:account:model-invocation-job/jobId
            job_identifier = invocation_arn
            
            logger.info(f"Stopping model invocation job: {job_identifier}")
            
            self.client.stop_model_invocation_job(
                jobIdentifier=job_identifier
            )
            
            logger.info(f"Successfully stopped model invocation job: {job_identifier}")
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            
            # Handle specific error cases
            if error_code == "ConflictException":
                # Job is not in a state that can be stopped (e.g., already completed)
                logger.warning(f"Cannot stop job {invocation_arn}: {error_message}")
                raise BedrockError(
                    f"Job cannot be stopped (may already be completed or failed): {error_message}"
                ) from e
            elif error_code == "ResourceNotFoundException":
                logger.error(f"Job not found: {invocation_arn}")
                raise BedrockError(f"Job not found: {error_message}") from e
            else:
                logger.error(f"Bedrock API error ({error_code}): {error_message}")
                raise BedrockError(
                    f"Failed to stop model invocation job: {error_message}"
                ) from e
        except Exception as e:
            logger.error(f"Unexpected error stopping job: {e}")
            raise BedrockError(
                f"Failed to stop model invocation job: {str(e)}"
            ) from e
    def invoke_claude(
        self,
        prompt: str,
        model_id: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> str:
        """Invoke Claude model for reasoning and planning tasks.

        This method uses Claude on Amazon Bedrock for orchestration tasks such as
        query intent classification, execution planning, and insight aggregation.

        Args:
            prompt: The prompt to send to Claude
            model_id: Claude model ID (optional, defaults to configured model with inference profile)
            temperature: Temperature for randomness (0-1, default: 0.2)
            max_tokens: Maximum tokens to generate (default: 4096)

        Returns:
            String containing Claude's response text

        Raises:
            BedrockError: If the API call fails
        """
        # Use configured Claude model ID if not specified
        if model_id is None:
            model_id = self.claude_model_id
        
        try:
            # Prepare request body for Claude Messages API format
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": temperature,
                "max_tokens": max_tokens
            }

            logger.debug(f"Invoking Claude model: {model_id}")
            logger.debug(f"Prompt: {prompt[:100]}...")

            # Invoke model
            response = self.client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body)
            )

            # Parse response
            response_body = json.loads(response["body"].read())

            # Extract text from response
            # Claude response format: {"content": [{"type": "text", "text": "..."}], ...}
            content = response_body.get("content", [])
            if not content or not isinstance(content, list) or len(content) == 0:
                logger.error(f"Invalid response structure. Full response: {response_body}")
                raise BedrockError(
                    f"Invalid response from Claude. Response keys: {list(response_body.keys())}"
                )

            # Extract text from first content block
            text = ""
            for block in content:
                if block.get("type") == "text":
                    text += block.get("text", "")

            if not text:
                logger.error(f"Empty text received. Full response: {response_body}")
                raise BedrockError(
                    f"Received empty text from Claude. Content: {content}"
                )

            logger.info(f"Claude invocation completed ({len(text)} characters)")

            return text

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_message = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Bedrock API error ({error_code}): {error_message}")
            raise BedrockError(
                f"Failed to invoke Claude: {error_message}"
            ) from e
        except Exception as e:
            logger.error(f"Unexpected error invoking Claude: {e}")
            raise BedrockError(
                f"Failed to invoke Claude: {str(e)}"
            ) from e
