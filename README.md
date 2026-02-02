# VigilaCore

<div align="center">

![Python](https://img.shields.io/badge/Python-33.3%25-3776AB?style=flat-square&logo=python&logoColor=white)
![HTML](https://img.shields.io/badge/HTML-47.6%25-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-18.8%25-1572B6?style=flat-square&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-0.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

**A monitoring and analytics platform for utility reading management**

</div>

---

## 📋 Overview

VigilaCore is a full-stack web application designed to monitor and analyze utility reading data. It provides dashboard metrics, chart visualizations, and detailed reports for tracking **Releitura** (re-reading) and **Porteira** (gateway) operations.

## ✨ Features

- 🔐 **User Authentication** - Secure login and registration system with role-based access control
- 📊 **Interactive Dashboards** - Real-time metrics and chart visualizations
- 📁 **Excel File Processing** - Upload and process Excel reports with automatic data extraction
- 🔄 **Portal Sync** - Automated data synchronization with external portals via web scraping
- 📈 **Analytics Engine** - Deep scan analysis for reading data with duplicate detection
- 👥 **Admin Controls** - Database reset capabilities for administrators

## 🤖 Automatic Scheduler

VigilaCore now includes a robust **automation system** that handles report downloads automatically from the CEMIG SGL portal.

- **⏰ Automated Downloads**: Configurable hourly intervals.
- **🔄 Sequential Execution**: Prevents conflicts by running Releitura and Porteira tasks sequentially.
- **📅 Custom Schedule**: Set specific operating hours (e.g., 7 AM to 5 PM).
- **📝 Detailed Logging**: Complete tracking of all automatic operations.

For full configuration details, please refer to the [Automation Guide](GUIA_SCHEDULER_AUTOMATICO.md) (Portuguese).

## 🏗️ Project Structure

```
VigilaCore/
├── backend/
│   ├── app.py              # Flask REST API server
│   ├── requirements.txt    # Python dependencies
│   ├── test_auth.py        # Authentication tests
│   ├── migrate_passwords.py
│   └── core/               # Core business logic modules
│       ├── analytics.py    # Data analysis functions
│       ├── database.py     # Database operations
│       ├── auth.py         # Authentication logic
│       ├── dashboard_metrics.py
│       ├── portal_scraper.py  # Web scraping for portal sync
│       └── scheduler.py    # Automation scheduler logic
├── frontend/
│   ├── views/              # HTML templates
│   ├── css/                # Stylesheets
│   └── js/                 # JavaScript files
└── data/                   # Uploaded Excel files
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- pip (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/hrsallan/VigilaCore.git
   cd VigilaCore
   ```

2. **Install dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Run the application**
   ```bash
   python app.py
   ```

4. **Access the application**
   
   Open your browser and navigate to `http://localhost:5000`

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` | User authentication |
| POST | `/api/register` | User registration |
| GET | `/api/status/releitura` | Get releitura status and metrics |
| GET | `/api/status/porteira` | Get porteira status and metrics |
| GET | `/api/dashboard/metrics` | Get dashboard metrics |
| POST | `/api/upload` | Upload Excel file for processing |
| POST | `/api/upload/porteira` | Upload porteira Excel file |
| POST | `/api/sync/releitura` | Sync releitura data from portal |
| POST | `/api/sync/porteira` | Sync porteira data from portal |
| GET | `/api/scheduler/status` | Get automation scheduler status |
| POST | `/api/scheduler/toggle` | Start/Stop scheduler (Admin only) |
| POST | `/api/reset` | Reset database (admin only) |
| POST | `/api/reset/porteira` | Reset porteira database (admin only) |
| GET | `/api/porteira/chart` | Get porteira chart data |
| GET | `/api/porteira/table` | Get porteira table data |

## 🛠️ Tech Stack

- **Backend**: Python, Flask, Flask-CORS
- **Frontend**: HTML5, CSS3, JavaScript
- **Data Processing**: Pandas, OpenPyXL, xlrd
- **Automation**: Selenium, PyAutoGUI, APScheduler
- **Configuration**: python-dotenv

## 📄 License

This project is available under a **Non-Commercial License**. You are free to use, modify, and distribute this software for non-commercial purposes only. Commercial use, including selling or using this software to generate revenue, is strictly prohibited. See the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to check the [issues page](https://github.com/hrsallan/VigilaCore/issues).

---

<div align="center">
Created by <a href="https://github.com/hrsallan">hrsallan</a>
</div>