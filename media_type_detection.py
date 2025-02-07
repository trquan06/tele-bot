from dataclasses import dataclass
from typing import Optional

@dataclass
class MediaInfo:
    type: str
    file_name: str
    file_size: int
    mime_type: Optional[str] = None

def get_media_type(message) -> Optional[MediaInfo]:
    """
    Enhanced media type detection for Telegram messages
    Returns MediaInfo object with type details
    """
    try:
        # Check for video
        if message.video:
            return MediaInfo(
                type="video",
                file_name=message.video.file_name if message.video.file_name else f"video_{message.video.file_id}.mp4",
                file_size=message.video.file_size,
                mime_type=message.video.mime_type
            )
        # Check for photo
        elif message.photo:
            # Get largest photo size
            photo = message.photo[-1]
            return MediaInfo(
                type="photo",
                file_name=f"photo_{photo.file_id}.jpg",
                file_size=photo.file_size,
                mime_type="image/jpeg"
            )
        # Check for document
        elif message.document:
            mime_type = message.document.mime_type
            # Determine type based on mime_type
            doc_type = "video" if mime_type and "video" in mime_type else "document"
            return MediaInfo(
                type=doc_type,
                file_name=message.document.file_name if message.document.file_name else f"doc_{message.document.file_id}",
                file_size=message.document.file_size,
                mime_type=mime_type
            )
        return None
    except Exception as e:
        print(f"Error in media type detection: {e}")
        return None