import os
import time
import uuid
import mimetypes
import asyncio
import aiohttp
import zipfile
from bs4 import BeautifulSoup
from pyrogram import errors
from config import BASE_DOWNLOAD_FOLDER, CHUNK_SIZE, SUPPORTED_MEDIA_TYPES, MAX_CONCURRENT_DOWNLOADS, MAX_RETRIES, EXTRACT_FOLDER, MAX_FILE_SIZE
from progress import progress_callback
from flood_control import handle_flood_wait
from pyrogram import Client
import patoolib
from media_type_detection import get_media_type, MediaInfo
# Semaphore to limit concurrent downloads
download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)

# Global list for tracking failed downloads
failed_files = []

async def download_from_url(message, url):
    """
    Downloads content from a URL. Supports:
      - HTML pages with media links (including Telegra.ph).
      - Direct file downloads.
      - If a .zip file is downloaded, it will automatically extract it.
    """
    failed_downloads = []
    connector = aiohttp.TCPConnector(limit=50, force_close=True)
    timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour timeout

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        try:
            async with session.get(url) as response:
                content_type = response.headers.get("Content-Type", "").lower()
                # If HTML, parse for media
                if response.status == 200 and "html" in content_type:
                    html_content = await response.text()
                    soup = BeautifulSoup(html_content, "html.parser")

                    # Handle Telegra.ph specifically
                    if "telegra.ph" in url:
                        media_links = [tag["src"] for tag in soup.find_all("img", src=True)]
                        if not media_links:
                            await message.reply("No images found on Telegra.ph URL.")
                            return
                        total_files = len(media_links)
                        status_msg = await message.reply(f"Downloading {total_files} files from Telegra.ph...")
                        for idx, media_url in enumerate(media_links, 1):
                            try:
                                if media_url.startswith("/"):
                                    media_url = f"https://telegra.ph{media_url}"
                                await download_from_url(message, media_url)
                                if idx % 5 == 0:
                                    await status_msg.edit_text(f"Downloaded {idx}/{total_files} files from Telegra.ph...")
                            except errors.FloodWait as e:
                                await handle_flood_wait(e, message)
                            except Exception as e:
                                failed_downloads.append((media_url, str(e)))
                        success_count = total_files - len(failed_downloads)
                        await status_msg.edit_text(
                            f"Completed Telegra.ph download:\n✅ Success: {success_count}\n❌ Failed: {len(failed_downloads)}"
                        )
                        return

                    # For other HTML pages, try to extract media links
                    media_links = [tag["src"] for tag in soup.find_all(["img", "video"], src=True)]
                    if media_links:
                        total_files = len(media_links)
                        status_msg = await message.reply(f"Downloading {total_files} media files...")
                        for idx, media_url in enumerate(media_links, 1):
                            try:
                                if not media_url.startswith("http"):
                                    media_url = os.path.join(os.path.dirname(url), media_url)
                                await download_from_url(message, media_url)
                                if idx % 5 == 0:
                                    await status_msg.edit_text(f"Downloaded {idx}/{total_files} media files...")
                            except errors.FloodWait as e:
                                await handle_flood_wait(e, message)
                            except Exception as e:
                                failed_downloads.append((media_url, str(e)))
                        success_count = total_files - len(failed_downloads)
                        await status_msg.edit_text(
                            f"Completed media download:\n✅ Success: {success_count}\n❌ Failed: {len(failed_downloads)}"
                        )
                        return
                    else:
                        await message.reply("No media found in the provided URL.")
                        return

                # Handle server errors
                if response.status == 500:
                    await message.reply(f"Server error (500) for URL: {url}. Try again later.")
                    return
                if response.status != 200:
                    await message.reply(f"Failed to download from URL: {url}\nStatus code: {response.status}")
                    return

                # Direct file download
                content_disp = response.headers.get("Content-Disposition", "")
                if "filename=" in content_disp:
                    file_name = content_disp.split("filename=")[-1].strip('"')
                else:
                    ext = mimetypes.guess_extension(content_type.split(";")[0]) or ""
                    file_name = f"{uuid.uuid4().hex}{ext}"
                file_path = os.path.join(BASE_DOWNLOAD_FOLDER, file_name)

                total_size = int(response.headers.get('Content-Length', 0))
                downloaded_size = 0
                start_time = time.time()
                status_msg = await message.reply("Starting file download...")
                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            current_time = time.time()
                            # Update progress every few seconds or on completion
                            if total_size > 0 and (downloaded_size / total_size * 100 % 5 == 0 or current_time - start_time >= 3):
                                progress = (downloaded_size / total_size * 100)
                                speed = downloaded_size / (current_time - start_time)
                                await status_msg.edit_text(
                                    f"Downloading file: {progress:.1f}%\nSpeed: {speed:.1f} bytes/s\nDownloaded: {downloaded_size} MB"
                                )
                await status_msg.edit_text(f"✅ Downloaded file from URL: {url}\nSaved at: {file_path}")
                
                # Verify file integrity
                if downloaded_size != total_size:
                    raise ValueError(f"Incomplete download: expected {total_size} bytes, got {downloaded_size} bytes")

                # --- NEW: If file is a compressed file, extract its contents ---
                if file_path.lower().endswith(('.zip', '.rar', '.tar', '.gz', '.7z')):
                    try:
                        if file_path.lower().endswith(".zip"):
                            with zipfile.ZipFile(file_path, "r") as zip_ref:
                                if len(zip_ref.namelist()) == 0:
                                    await message.reply(f"❌ The .zip file is empty: {file_path}")
                                else:
                                    zip_ref.extractall(EXTRACT_FOLDER)
                        else:
                            patoolib.extract_archive(file_path, outdir=EXTRACT_FOLDER)
                        await message.reply(f"✅ Compressed file extracted into {EXTRACT_FOLDER}")
                    except Exception as extract_err:
                        await message.reply(f"❌ Error extracting compressed file: {extract_err}")

        except errors.FloodWait as e:
            await handle_flood_wait(e, message)
        except aiohttp.ClientError as e:
            await message.reply(f"Connection error while downloading: {str(e)}")
        except Exception as e:
            await message.reply(f"Error while downloading from URL: {str(e)}")
        if failed_downloads:
            error_report = "Failed downloads:\n"
            for link, err in failed_downloads:
                error_report += f"- {link}: {err}\n"
            await message.reply(error_report)

async def download_with_progress(message, media_type, retry=False, max_retries=MAX_RETRIES):
    """Enhanced download function with better media type detection"""
    global failed_files

    try:
        # Get media info using new detection logic
        media_info = get_media_type(message)
        if not media_info:
            raise ValueError(f"Không tìm thấy media hợp lệ trong tin nhắn")

        # Verify file size
        if not await verify_file_size(message):
            raise DownloadError("File size verification failed")

        # Use detected media info
        file_path = os.path.join(
            BASE_DOWNLOAD_FOLDER,
            f"{os.path.splitext(media_info.file_name)[0]}_{uuid.uuid4().hex[:8]}{os.path.splitext(media_info.file_name)[1]}"
        )

        async with download_semaphore:
            status_message = await message.reply(
                f"Bắt đầu tải {media_info.type}...\n"
                f"Tên file: {media_info.file_name}\n"
                f"Kích thước: {media_info.file_size/(1024*1024):.1f} MB"
            )
            start_time = time.time()

            try:
                # Enhanced download with chunked transfer
                download_task = asyncio.create_task(
                    message.download(
                        file_name=file_path,
                        progress=lambda current, total: asyncio.create_task(
                            progress_callback(current, total, status_message, start_time, media_info.type)
                        ),
                        block=True
                    )
                )

                await asyncio.wait_for(download_task, timeout=DOWNLOAD_TIMEOUT)

                # Verify downloaded file
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    if file_size == 0:
                        raise DownloadError("Downloaded file is empty")

                    # Update status message with success
                    await status_message.edit_text(
                        f"✅ {media_info.type.capitalize()} tải xuống thành công!\n"
                        f"📁 File: {os.path.basename(file_path)}\n"
                        f"📊 Kích thước: {file_size/(1024*1024):.1f} MB"
                    )

                    # Remove from failed_files if this was a retry
                    if retry:
                        failed_files = [f for f in failed_files if f["file_path"] != file_path]

                    return True

            except asyncio.TimeoutError:
                raise DownloadError("Download timed out")
            except errors.FloodWait as e:
                await handle_flood_wait(e, message)
                raise
            except Exception as e:
                raise DownloadError(f"Download error: {str(e)}")

    except Exception as e:
        error_msg = f"❌ Lỗi khi tải {media_type}: {str(e)}"
        logger.error(error_msg)
        
        if not retry:
            failed_files.append({
                "file_path": file_path,
                "message": message,
                "media_type": media_type,
                "error": str(e)
            })
            
        try:
            await status_message.edit_text(
                f"{error_msg}\n"
                "Sử dụng /retry_download để thử tải lại."
            )
        except Exception as edit_error:
            logger.error(f"Error updating status message: {str(edit_error)}")

        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
            
        return False
        # Create a unique filename to avoid overwriting
        import os, uuid
        base_name, ext = os.path.splitext(file_name)
        unique_name = f"{base_name}_{uuid.uuid4().hex[:8]}{ext}"
        file_path = os.path.join(BASE_DOWNLOAD_FOLDER, unique_name)

        async with download_semaphore:
            status_message = await message.reply(f"Starting download of {media_type}...")
            start_time = time.time()
            current_try = 0

            while current_try < max_retries:
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    # Wrap download_media call to catch socket.send exceptions
                    await message.download(
                        file_name=file_path,
                        progress=lambda current, total: asyncio.create_task(
                            progress_callback(current, total, status_message, start_time, media_type)
                        ),
                        block=True
                    )
                    # Verify download
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                        await status_message.edit_text(
                            f"✅ {media_type.capitalize()} downloaded successfully!\n"
                            f"File: {unique_name}\n"
                            f"Size: {os.path.getsize(file_path)} bytes"
                        )
                        # Remove from failed_files if this was a retry
                        if retry:
                            failed_files = [f for f in failed_files if f["file_path"] != file_path]
                        
                        # --- NEW: If file is a compressed file, extract its contents ---
                        if file_path.lower().endswith(('.zip', '.rar', '.tar', '.gz', '.7z')):
                            try:
                                if file_path.lower().endswith(".zip"):
                                    with zipfile.ZipFile(file_path, "r") as zip_ref:
                                        if len(zip_ref.namelist()) == 0:
                                            await message.reply(f"❌ The .zip file is empty: {file_path}")
                                        else:
                                            zip_ref.extractall(EXTRACT_FOLDER)
                                else:
                                    patoolib.extract_archive(file_path, outdir=EXTRACT_FOLDER)
                                await message.reply(f"✅ Compressed file extracted into {EXTRACT_FOLDER}")
                            except Exception as extract_err:
                                await message.reply(f"❌ Error extracting compressed file: {extract_err}")

                        return True
                    raise ValueError("Downloaded file is invalid.")

                except errors.FloodWait as e:
                    await handle_flood_wait(e, message)
                    current_try += 1
                    if current_try < max_retries:
                        await status_message.edit_text(
                            f"FloodWait encountered. Retrying {current_try + 1}/{max_retries}..."
                        )
                        await asyncio.sleep(retry_delay)
                except Exception as e:
                    current_try += 1
                    if current_try < max_retries:
                        await status_message.edit_text(
                            f"Error: {str(e)}\nRetrying {current_try + 1}/{max_retries}..."
                        )
                        await asyncio.sleep(retry_delay)
                    else:
                        raise e

            raise Exception("Exceeded maximum retry attempts.")

    except Exception as e:
        error_msg = f"❌ Error downloading {media_type}: {str(e)}"
        print("Download error:", error_msg)
        if not retry:
            failed_files.append({
                "file_path": file_path,
                "message": message,
                "media_type": media_type,
                "error": str(e)
            })
        try:
            await status_message.edit_text(
                f"{error_msg}\nUse /retry_download to attempt manual re-download."
            )
        except Exception:
            pass
        if os.path.exists(file_path):
            os.remove(file_path)
        return False
