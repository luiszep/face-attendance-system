import boto3
import os
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import numpy as np
import cv2
import io
from botocore.config import Config


# Load environment variables from .env file
from pathlib import Path
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)

# AWS Config
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_S3_BUCKET_NAME = os.getenv("AWS_S3_BUCKET_NAME")
AWS_S3_REGION = os.getenv("AWS_S3_REGION")

# Force path-style addressing
config = Config(
    signature_version='s3v4',
    s3={'addressing_style': 'path'}  # <-- Add this
)

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_S3_REGION,
    config=config  # <-- Use this updated config
)

def upload_file_to_s3(file_obj, folder="uploads"):
    """
    Uploads a file object (like from Flask's request.files) to S3.
    Returns the full S3 key if successful, or None if failed.
    """
    try:
        filename = secure_filename(file_obj.filename)
        s3_key = f"{folder}/{filename}"
        s3.upload_fileobj(file_obj, AWS_S3_BUCKET_NAME, s3_key)
        return s3_key
    except Exception as e:
        print("Error uploading to S3:", e)
        return None

def list_files_in_folder(prefix):
    """
    List files under a given S3 folder (prefix).
    Returns a list of filenames (not full S3 keys).
    """
    try:
        response = s3.list_objects_v2(Bucket=AWS_S3_BUCKET_NAME, Prefix=prefix + "/")
        contents = response.get("Contents", [])
        return [obj["Key"].split("/")[-1] for obj in contents if not obj["Key"].endswith("/")]
    except Exception as e:
        print("S3 list error:", e)
        return []

def load_image_from_s3(s3_key):
    """
    Download an image file from S3 and convert it to an OpenCV image (NumPy array).
    Returns: image array or None if failed.
    """
    try:
        response = s3.get_object(Bucket=AWS_S3_BUCKET_NAME, Key=s3_key)
        img_bytes = response['Body'].read()
        img_array = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print(f"[S3 Error] Failed to load image {s3_key}: {e}")
        return None
    
def generate_presigned_url(s3_key, expiration=3600):
    """
    Generate a presigned URL to access a file in S3.
    """
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': AWS_S3_BUCKET_NAME, 'Key': s3_key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        print("Presigned URL error:", e)
        return None
