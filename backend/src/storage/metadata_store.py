"""Metadata storage for video indexes.

This module provides persistent storage for index metadata using S3.
"""

import json
import logging
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client as S3ClientType

try:
    from models.index import Index
except ImportError:
    from ..models.index import Index

logger = logging.getLogger(__name__)

# S3 key for indexes metadata
INDEXES_S3_KEY = "metadata/indexes.json"


class IndexMetadataStore:
    """Persists index metadata using S3 storage.
    
    This class handles saving, loading, and managing index metadata in S3.
    
    Attributes:
        s3_client: Boto3 S3 client
        bucket_name: S3 bucket name for storage
        s3_key: S3 key for the indexes JSON file
    """
    
    def __init__(
        self,
        s3_client: "S3ClientType",
        bucket_name: str,
        storage_path: Optional[str] = None  # Deprecated, kept for compatibility
    ):
        """Initialize the metadata store.
        
        Args:
            s3_client: Boto3 S3 client instance
            bucket_name: S3 bucket name for storing metadata
            storage_path: Deprecated parameter, ignored
        """
        self.s3_client = s3_client
        self.bucket_name = bucket_name
        self.s3_key = INDEXES_S3_KEY
        
        logger.info(f"IndexMetadataStore initialized with S3: s3://{bucket_name}/{self.s3_key}")
        self._ensure_storage_exists()
    
    def _ensure_storage_exists(self) -> None:
        """Create the indexes file in S3 if it doesn't exist."""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=self.s3_key)
        except self.s3_client.exceptions.ClientError as e:
            if e.response['Error']['Code'] == '404':
                # File doesn't exist, create empty indexes
                self._write_indexes([])
                logger.info(f"Created empty indexes file at s3://{self.bucket_name}/{self.s3_key}")
            else:
                raise
    
    def _read_indexes(self) -> List[dict]:
        """Read raw index data from S3.
        
        Returns:
            List of index dictionaries
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=self.s3_key
            )
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        except self.s3_client.exceptions.NoSuchKey:
            return []
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON in {self.s3_key}, returning empty list")
            return []
        except Exception as e:
            logger.error(f"Error reading indexes from S3: {e}")
            return []
    
    def _write_indexes(self, indexes: List[dict]) -> None:
        """Write index data to S3.
        
        Args:
            indexes: List of index dictionaries to write
        """
        content = json.dumps(indexes, indent=2)
        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=self.s3_key,
            Body=content.encode('utf-8'),
            ContentType='application/json'
        )
    
    def save_index(self, index: Index) -> None:
        """Save or update an index in the metadata store.
        
        If an index with the same ID already exists, it will be updated.
        Otherwise, a new index entry will be created.
        
        Args:
            index: Index instance to save
        """
        indexes = self._read_indexes()
        
        # Convert index to dictionary using Pydantic's model_dump
        index_dict = index.model_dump(mode='json')
        
        # Check if index already exists and update it
        updated = False
        for i, existing in enumerate(indexes):
            if existing.get('id') == index.id:
                indexes[i] = index_dict
                updated = True
                break
        
        # If not updated, append new index
        if not updated:
            indexes.append(index_dict)
        
        self._write_indexes(indexes)
    
    def load_indexes(self) -> List[Index]:
        """Load all indexes from the metadata store.
        
        Returns:
            List of Index instances
        """
        indexes_data = self._read_indexes()
        return [Index.model_validate(data) for data in indexes_data]
    
    def delete_index(self, index_id: str) -> None:
        """Delete an index from the metadata store.
        
        Args:
            index_id: ID of the index to delete
        """
        indexes = self._read_indexes()
        
        # Filter out the index with matching ID
        indexes = [idx for idx in indexes if idx.get('id') != index_id]
        
        self._write_indexes(indexes)
    
    def get_index(self, index_id: str) -> Optional[Index]:
        """Retrieve a specific index by ID.
        
        Args:
            index_id: ID of the index to retrieve
            
        Returns:
            Index instance if found, None otherwise
        """
        indexes = self._read_indexes()
        
        for index_data in indexes:
            if index_data.get('id') == index_id:
                return Index.model_validate(index_data)
        
        return None
