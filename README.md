---
title: Church Assistant
emoji: ⛪
colorFrom: blue
colorTo: indigo
sdk: docker
pinned: false
---

# ⛪ AI Church Chatbot

> **A Universal, Multi-Tenant AI Assistant for Church Websites.**  
> *Powered by RAG (Retrieval-Augmented Generation), FastAPI, and Web Components.*

![Status](https://img.shields.io/badge/Status-Active-success)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Backend](https://img.shields.io/badge/Backend-FastAPI-green)
![Frontend](https://img.shields.io/badge/Frontend-Web_Component-orange)

## 📖 Overview

The **AI Church Chatbot** is a turnkey solution designed to be embedded on any church website. It ingests public website content (service times, ministries, events) and uses an LLM to answer visitor questions accurately, acting as a digital greeter 24/7.

**Key Features:**
*   **🕷️ Smart Scraper**: Asynchronously crawls church websites, cleaning boilerplate to extract high-quality knowledge.
*   **🧠 RAG Architecture**: Uses a local Vector Database (ChromaDB) to retrieve relevant context before answering.
*   **🏢 Multi-Tenancy**: Support for multiple churches on a single server instance. Context is isolated by `church_id`.
*   **🛡️ Hallucination Guard**: strict link validation ensures the bot never invents fake URLs.
*   **🔌 Plug-and-Play Widget**: A single generic JavaScript file (`church_chatbot.js`) provides a beautiful, modern chat interface for any site.

---

## 🚀 Quick Start

### 1. Installation

Ensure you have **Python 3.10+** installed.

```bash
# Clone the repository (if applicable)
git clone ...

# Install dependencies
pip install -r requirements.txt
```

### 2. Configuration

Create a `.env` file in the root directory with your OpenAI API key:

```ini
OPENAI_API_KEY=sk-proj-YOUR_KEY_HERE
```

### 3. Ingesting Church Data

The chatbot needs to "learn" about a church before it can answer questions. Use the ingestion script with a unique `church_id`.

**Example:**
Scrape and ingest data for a generic example church (or your own).
*Note: You must first run `webscrape.py` or provide a `jsonl` file. For this demo, we assume `scraped_data.jsonl` exists.*

```bash
cd code
# "Clean" ingest (removes old data for this ID if it exists)
python ingest.py --church_id my_church --input_file ../scraped_data.jsonl
```

### 4. Running the Server

Start the FastAPI backend:

```bash
cd code
python server.py
```
The server will start at `http://localhost:8004`.

---

## 💻 Frontend Integration

The chatbot is delivered as a **Custom Web Component** `<church-chatbot>`. This makes it framework-agnostic and easy to embed anywhere (WordPress, Squarespace, React, static HTML).

### Basic Embed Code

Add this to your website's footer:

```html
<!-- 1. Load the Script -->
<script src="http://localhost:8004/church_chatbot.js" defer></script>

<!-- 2. Sort the Component -->
<church-chatbot 
    api-url="http://localhost:8004/chat"
    church-id="my_church"
    title="Church Assistant"
></church-chatbot>
```

### Component Attributes

| Attribute | Description | Default |
| :--- | :--- | :--- |
| `api-url` | Full URL to the backend chat endpoint. | `http://localhost:8004/chat` |
| `church-id` | **Required for multi-tenancy.** Matches the ID used during ingestion. | `null` |
| `title` | The text displayed in the chat header. | `Church Assistant` |
| `greeting` | The initial welcoming message. | *"Hi there!..."* |
| `logo-svg` | (Advanced) Custom SVG XML to replace the default icon. | *Generic Church Icon* |

---

## 📂 Project Structure

```text
├── code/
│   ├── server.py           # FastAPI Backend & Static File Server
│   ├── ingest.py           # Vector DB Ingestion Script
│   ├── webscrape.py        # Web Crawler
│   ├── retrieval.py        # RAG Logic & Context Retrieval
│   ├── church_chatbot.js   # Frontend Web Component
│   ├── widget_demo.html    # Local Demo Page
│   ├── link_utils.py       # Helper for URL validation
│   └── context_manager.py  # Helper for context loading
├── chroma_db/              # Local Vector Database Storage
├── churches.json           # Registry of configured churches
└── requirements.txt        # Python Dependencies
```

## 🛠️ Development

To test locally without embedding:
1.  Run the server: `python code/server.py`
2.  Open `http://localhost:8004` in your browser.
3.  This loads `code/widget_demo.html`, which is pre-configured to talk to your local backend.