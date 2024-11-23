# 🎵 Trackster 🎵

Welcome to **Trackster**! Trackster is a funky Flet app that allows you to download playlists from Spotify and YouTube. 🎧✨

## Features
- 📥 Download entire playlists from YouTube and Spotify.
- 🎨 User-friendly interface with a cool progress bar.
- 🖼️ Automatically adds metadata and album art to your downloaded tracks.
- 🔍 Search for tracks on Spotify and YouTube.
- 🛠️ Customizable settings for file handling.

<img src="https://github.com/user-attachments/assets/7e98cdb5-61f2-48bb-a2cb-b6d45ffee827" width="400"> <img src="https://github.com/user-attachments/assets/084acca0-9ef8-4e8e-81f0-cc84d9effeab" width="400">

## How to Run the App

### Option 1: Run from Source
1. Clone the repository:
    ```sh
    git clone https://github.com/yourusername/Trackster.git
    cd Trackster
    ```

2. Install the required dependencies:
    ```sh
    pip install -r requirements.txt
    ```

3. Run the app:
    ```sh
    flet run main.py
    ```

### Option 2: Download Executable
1. Go to the [Releases](https://github.com/shouryashashank/Trackster/releases) page.
2. Download the latest executable file for your operating system.
    - **Trackster.exe**: Use this for regular downloads.
    - **Trackster_debug.exe**: Use this when downloading from playlists containing more than 500 songs, as it helps manage songs that fail to download due to connection issues.

3. Run the downloaded executable file to start the app.

### Supported Platforms
- Currently supported: **Windows**, **Linux**
- Coming soon: **Android**

**Help Needed**: If you can help compile Trackster for macOS and iOS, please reach out or contribute to the project. Your assistance would be greatly appreciated!

## Usage
1. **Select Output Directory**: Choose the folder where you want to save your downloaded music.
2. **Enter Playlist URL**: Input the URL of the YouTube or Spotify playlist you want to download.
3. **Choose File Handling Option**: Decide what to do if a file already exists (Replace all, Skip all).
4. **Download**: Click the "Download Playlist" button and let Trackster do the magic! 🎩✨
   
### Adding Spotify API Keys
You can add your Spotify API keys through the app's settings:
1. Click on the hamburger menu in the top right corner.
2. Enter your Spotify Client ID and Client Secret in the provided fields.
3. Click "Save" to update the settings.
   
## Limitations
- **No Proper Continue Option**: You can pause and resume downloads by restarting the app, but it takes some time to re-initiate and could be improved.

## Disclaimer
**Support the Artists**: This tool is intended for personal use only. Please support the artists by purchasing their music or streaming it through official channels. 💖🎶

---

Enjoy your music with Trackster! 🎉🎵
