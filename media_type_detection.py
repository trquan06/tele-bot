from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class MediaInfo:
    """Class to store media file information"""
    type: str
    file_name: str
    file_size: int
    mime_type: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None

def get_media_type(message) -> Optional[MediaInfo]:
    """
    Detects the type of media in a message and returns relevant information
    """
    try:
        # Handle photo
        if message.photo:
            photo = message.photo
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_name = f"photo_{timestamp}.jpg"
            return MediaInfo(
                type="photo",
                file_name=file_name,
                file_size=photo.file_size,
                mime_type="image/jpeg",
                width=photo.width,
                height=photo.height
            )
        
        # Handle video
        elif message.video:
            video = message.video
            file_name = video.file_name or f"video_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
            return MediaInfo(
                type="video",
                file_name=file_name,
                file_size=video.file_size,
                mime_type=video.mime_type,
                width=video.width,
                height=video.height
            )
        
        # Handle document
        elif message.document:
            doc = message.document
            file_name = doc.file_name or f"document_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            return MediaInfo(
                type="document",
                file_name=file_name,
                file_size=doc.file_size,
                mime_type=doc.mime_type
            )
        # Handle forwarded photo
        elif message.forward_date and message.photo:
            photo = message.photo
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_name = f"forwarded_photo_{timestamp}.jpg"
            return MediaInfo(
                type="photo",
                file_name=file_name,
                file_size=photo.file_size,
                mime_type="image/jpeg",
                width=photo.width,
                height=photo.height
            )

        # Handle forwarded video
        elif message.forward_date and message.video:
            video = message.video
            file_name = video.file_name or f"forwarded_video_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.mp4"
            return MediaInfo(
                type="video",
                file_name=file_name,
                file_size=video.file_size,
                mime_type=video.mime_type,
                width=video.width,
                height=video.height
            )

        # Handle forwarded document
        elif message.forward_date and message.document:
            doc = message.document
            file_name = doc.file_name or f"forwarded_document_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            return MediaInfo(
                type="document",
                file_name=file_name,
                file_size=doc.file_size,
                mime_type=doc.mime_type
            )

        return None

    except Exception as e:
        print(f"Error in get_media_type: {str(e)}")
        return None
