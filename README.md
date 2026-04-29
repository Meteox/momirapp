# Momir Command Center v0.1 🧙‍♂️🖨️

A complete software suite for an automated **Magic: The Gathering Momir Basic** physical play system. This project allows users to roll random cards via a web interface and automatically print them using a Raspberry Pi connected to a thermal printer.

## 🚀 System Architecture

### 1. Flask Server (`momir_server.py`)
The central hub running on a server:
* Manages the card database and image assets.
* Provides a REST API for the Raspberry Pi (`/api/pi_poll`, `/api/sync/manifest`).
* Handles the print queue and web dashboard.

### 2. Pi Client (`momir_pi.py`)
Control software for the Raspberry Pi:
* **Hardware:** Manages an SSD1306 OLED display, physical buttons, and a serial thermal printer.
* **Sync Engine:** Automatically downloads new cards/images from the server to the local `~/momirapp/www` directory.
* **Offline Mode:** Supports rolling cards directly via physical buttons without the web interface.

### 3. Scraper (`scraper.py`)
An automation tool to build your local database:
* Fetches data from the **Scryfall API**.
* Organizes cards by CMC (Converted Mana Cost) and categories (Creatures, Lands, etc.).
* Processes images (grayscale conversion & resizing) optimized for thermal printing.

## 📂 Project Structure
```text
momirapp/
├── momir_server.py    # Flask API & Webserver
├── momir_pi.py        # Raspberry Pi Client Logic
├── scraper.py         # Data Crawler for Scryfall
├── templates/         
│   └── index.html     # Mobile-friendly Web Interface
└── .gitignore         # Excludes local image assets (www/) from the repo
