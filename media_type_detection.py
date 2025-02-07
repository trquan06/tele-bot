from dataclasses import dataclass
from typing import Optional

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
    
    Args:
        message: The Pyrogram message object containing media
        
    Returns:
        MediaInfo object containing media details or None if no valid media found
    """
    try:
        if message.photo:
            # Get the largest photo size
            photo = message.photo
            file_name = f"photo_{message.date}.jpg"
            return MediaInfo(
                type="photo",
                file_name=file_name,
                file_size=photo.file_size,
                mime_type="image/jpeg",
                width=photo.width,
                height=photo.height
            )
            
        elif message.video:
            video = message.video
            file_name = video.file_name or f"video_{message.date}.mp4"
            return MediaInfo(
                type="video",
                file_name=file_name,
                file_size=video.file_size,
                mime_type=video.mime_type,
                width=video.width,
                height=video.height
            )
            
        elif message.document:
            doc = message.document
            file_name = doc.file_name or f"document_{message.date}"
            return MediaInfo(
                type="document",
                file_name=file_name,
                file_size=doc.file_size,
                mime_type=doc.mime_type
            )
            
        elif message.animation:
            anim = message.animation
            file_name = anim.file_name or f"animation_{message.date}.gif"
            return MediaInfo(
                type="animation",
                file_name=file_name,
                file_size=anim.file_size,
                mime_type=anim.mime_type,
                width=anim.width,
                height=anim.height
            )
            
        # Add other media types as needed
        
        return None
            
    except Exception as e:
        print(f"Error in get_media_type: {str(e)}")
        return None
