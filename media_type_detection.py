import os
from typing import Dict, Optional
from config import SUPPORTED_MEDIA_TYPES

class MediaInfo:
    def __init__(self, type: str, media: any, file_name: str, mime_type: str, file_size: int):
        self.type = type
        self.media = media 
        self.file_name = file_name
        self.mime_type = mime_type
        self.file_size = file_size

def get_media_type(message) -> Optional[MediaInfo]:
    """
    Detect media type and extract relevant information from message.
    Returns None if no supported media is found.
    """
    try:
        # Check for video
        if message.video:
            return MediaInfo(
                type="video",
                media=message.video,
                file_name=getattr(message.video, 'file_name', None) or f"video_{message.video.file_unique_id}.mp4",
                mime_type=getattr(message.video, 'mime_type', 'video/mp4'),
                file_size=message.video.file_size
            )
            
        # Check for photo
        elif message.photo:
            photo = message.photo[-1] if isinstance(message.photo, list) else message.photo
            return MediaInfo(
                type="ảnh",
                media=photo,
                file_name=f"photo_{photo.file_unique_id}.jpg",
                mime_type="image/jpeg",
                file_size=photo.file_size
            )
            
        # Check for document
        elif message.document:
            file_name = message.document.file_name
            if not file_name:
                return None
                
            ext = os.path.splitext(file_name)[1].lower()
            # Check if document extension is supported
            for media_type, extensions in SUPPORTED_MEDIA_TYPES.items():
                if ext in extensions:
                    return MediaInfo(
                        type=media_type,
                        media=message.document,
                        file_name=file_name,
                        mime_type=getattr(message.document, 'mime_type', ''),
                        file_size=message.document.file_size
                    )
        return None
        
    except Exception as e:
        logger.error(f"Error detecting media type: {str(e)}")
        return None

def is_supported_media_type(file_name: str) -> bool:
    """
    Check if the file extension is supported
    """
    ext = os.path.splitext(file_name)[1].lower()
    return any(ext in extensions for extensions in SUPPORTED_MEDIA_TYPES.values())

def get_mime_type(file_name: str) -> str:
    """
    Get MIME type based on file extension
    """
    ext = os.path.splitext(file_name)[1].lower()
    mime_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.mp4': 'video/mp4',
        '.avi': 'video/x-msvideo',
        '.mkv': 'video/x-matroska',
        '.mov': 'video/quicktime',
        '.webm': 'video/webm'
    }
    return mime_types.get(ext, 'application/octet-stream')