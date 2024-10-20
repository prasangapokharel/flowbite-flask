import os
import zipfile
from flask import Flask, request, render_template, send_file
import yt_dlp
from pydub import AudioSegment
from concurrent.futures import ThreadPoolExecutor
import multiprocessing

app = Flask(__name__)

# Dynamically set max workers based on system's CPU count to optimize performance
executor = ThreadPoolExecutor(max_workers=min(32, (multiprocessing.cpu_count() or 1) * 5))

def download_and_convert(url, output_dir='/tmp'):
    """
    Downloads YouTube audio and converts it directly to MP3 format using yt-dlp and pydub.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(output_dir, '%(title)s.%(ext)s'),
        'noplaylist': True,  # Prevent downloading entire playlists (for speed)
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',  # Directly download as MP3
            'preferredquality': '192',
        }],
        'concurrent-fragments': 5,  # Increase download concurrency for fragmented videos
        'quiet': True,  # Reduce logging output
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            # Construct MP3 file path
            filename = ydl.prepare_filename(info_dict)
            mp3_file = filename.replace('.webm', '.mp3').replace('.m4a', '.mp3').replace('.mp4', '.mp3')
    except Exception as e:
        print(f"Error downloading {url}: {str(e)}")
        return None

    return mp3_file

def zip_files(file_list, output_dir='/tmp'):
    """
    Zips a list of files into one archive.
    
    Args:
        file_list (list): List of file paths to zip.
        
    Returns:
        str: Path to the zip file.
    """
    zip_filename = os.path.join(output_dir, 'downloaded_mp3s.zip')
    with zipfile.ZipFile(zip_filename, 'w') as zipf:
        for file in file_list:
            if file and os.path.exists(file):  # Check if file exists before adding to zip
                zipf.write(file, os.path.basename(file))
    return zip_filename

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/download', methods=['POST'])
def download():
    urls = request.form.get('urls')
    if not urls:
        return "No URLs provided", 400
    
    try:
        url_list = [url.strip() for url in urls.split(',')]  # Split URLs by comma
        
        # Concurrently download and convert each video
        futures = [executor.submit(download_and_convert, url) for url in url_list]
        mp3_files = [future.result() for future in futures]  # Gather results
        
        # Filter out any failed downloads
        mp3_files = [f for f in mp3_files if f]
        
        if not mp3_files:
            return "No valid MP3 files were downloaded", 500
        
        # Zip the MP3 files into one archive
        zip_file = zip_files(mp3_files)
        
        # Send the zip file for download
        return send_file(zip_file, as_attachment=True)
    except Exception as e:
        return f"An error occurred: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
