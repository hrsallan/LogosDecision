# VigilaCore

<div align="center">

![Python](https://img.shields.io/badge/Python-31.0%25-3776AB?style=flat-square&logo=python&logoColor=white)
![HTML](https://img.shields.io/badge/HTML-53.1%25-E34F26?style=flat-square&logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-14.6%25-1572B6?style=flat-square&logo=css3&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-1.3%25-F7DF1E?style=flat-square&logo=javascript&logoColor=black)

**A monitoring and analytics platform for utility reading management**

[🇧🇷 Versão em Português](README.pt-BR.md) | [📖 Scheduler Guide](GUIA_SCHEDULER_AUTOMATICO.md)

</div>

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [Screenshots](#-screenshots)
- [Project Architecture](#️-project-architecture)
- [Getting Started](#-getting-started)
- [API Documentation](#-api-documentation)
- [Environment Variables](#-environment-variables)
- [Security Guide](#-security-guide)
- [Tech Stack](#️-tech-stack)
- [Contributing](#-contributing)
- [License](#-license)

---

## 📋 Overview

VigilaCore is a comprehensive full-stack web application specifically developed to monitor and analyze utility reading data for **CEMIG (Companhia Energética de Minas Gerais)** through their **SGL (Sistema de Gestão de Leitura)** portal.

The system automates the tedious process of manually downloading, processing, and analyzing reading reports, providing real-time dashboards, metrics, and visualizations for two critical operational workflows:

- **Releitura** (Re-reading): Tracks and manages meter re-reading operations when initial readings are questioned or require verification
- **Porteira** (Gateway): Monitors scheduled reading operations and execution status across different service points

### Key Business Value

- **Eliminates manual work**: Automated downloads from CEMIG SGL portal via scheduled synchronization
- **Real-time visibility**: Live dashboards showing current status of readings and operations
- **Historical tracking**: Complete audit trail of all reading operations over time
- **Duplicate detection**: Intelligent algorithms to identify and flag duplicate readings
- **Performance metrics**: KPIs and analytics to measure operational efficiency

## ✨ Features

- 🔐 **User Authentication** - Secure login and registration system with role-based access control (admin/user)
- 📊 **Interactive Dashboards** - Real-time metrics, KPIs, and chart visualizations updated automatically
- 📁 **Excel File Processing** - Upload and process Excel reports from CEMIG SGL with automatic data extraction
- 🔄 **Automated Portal Sync** - Scheduled downloads from CEMIG SGL portal using Selenium-based web scraping
- 📈 **Advanced Analytics Engine** - Deep scan analysis for reading data with intelligent duplicate detection
- ⏰ **Smart Scheduler** - Configurable automatic downloads at specified intervals during business hours
- 🗄️ **User Credential Management** - Store and manage portal credentials securely per user
- 📉 **Chart Visualizations** - Dynamic charts showing trends and execution status over time
- 👥 **Admin Controls** - Database reset capabilities and scheduler management for administrators
- 🔍 **Detailed Reporting** - Comprehensive tables showing individual reading records and execution details

## 📸 Screenshots

_Coming soon - Screenshots of dashboard, charts, and main features will be added here_

## 🏗️ Project Architecture

```
VigilaCore/
├── backend/
│   ├── app.py                    # Flask REST API server with all endpoints
│   ├── scheduler.py              # APScheduler automation for portal downloads
│   ├── requirements.txt          # Python dependencies
│   ├── test_auth.py              # Authentication unit tests
│   ├── migrate_passwords.py      # Database migration utility
│   ├── .env                      # Environment configuration (not in repo)
│   ├── core/                     # Core business logic modules
│   │   ├── analytics.py          # Data analysis and duplicate detection
│   │   ├── database.py           # SQLite database operations
│   │   ├── auth.py               # Authentication and authorization
│   │   ├── dashboard_metrics.py  # Metrics calculation for dashboards
│   │   └── portal_scraper.py     # Selenium-based CEMIG SGL scraper
│   └── data/
│       ├── vigilacore.db         # SQLite database
│       └── exports/              # Downloaded Excel files from portal
├── frontend/
│   ├── views/                    # HTML templates
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── releitura.html
│   │   └── porteira.html
│   ├── css/                      # Stylesheets
│   │   └── styles.css
│   └── js/                       # JavaScript files
│       └── app.js
└── docs/
    ├── README.md                 # This file
    ├── README.pt-BR.md           # Portuguese version
    └── GUIA_SCHEDULER_AUTOMATICO.md  # Scheduler guide
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Google Chrome (for Selenium automation)
- ChromeDriver (automatically managed by webdriver-manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/hrsallan/VigilaCore.git
   cd VigilaCore
   ```

2. **Install Python dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   nano .env  # Edit with your preferred editor
   ```
   
   See [Environment Variables](#-environment-variables) section for details.

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Access the application**
   
   Open your browser and navigate to `http://localhost:5000`

6. **Create your first user**
   
   Register a new account through the web interface. The first user created automatically receives admin privileges.

## 📡 API Documentation

Complete REST API reference with all 19 endpoints organized by functional category.

### Authentication

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/register` | Register a new user account | No |
| POST | `/api/login` | Authenticate user and receive session token | No |

**Example Request - Register:**
```json
POST /api/register
{
  "username": "john.doe",
  "password": "SecurePass123",
  "role": "user"
}
```

**Example Request - Login:**
```json
POST /api/login
{
  "username": "john.doe",
  "password": "SecurePass123"
}
```

### Dashboard & Metrics

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/ping` | Health check endpoint | No |
| GET | `/api/dashboard/metrics` | Get comprehensive dashboard metrics | Yes |
| GET | `/api/status/releitura` | Get releitura status, metrics, and recent activity | Yes |
| GET | `/api/status/porteira` | Get porteira status, metrics, and execution data | Yes |

**Example Response - Dashboard Metrics:**
```json
{
  "releitura": {
    "total": 156,
    "pending": 23,
    "completed": 133
  },
  "porteira": {
    "total": 89,
    "executed": 67,
    "not_executed": 22
  },
  "last_sync": "2026-02-02T10:30:00"
}
```

### Releitura Operations

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/upload` | Upload releitura Excel file for processing | Yes |
| POST | `/api/sync/releitura` | Trigger manual sync from CEMIG SGL portal | Yes |
| POST | `/api/reset` | Reset releitura database (admin only) | Yes (Admin) |

**Example Request - Upload:**
```bash
POST /api/upload
Content-Type: multipart/form-data

file: releitura_report.xlsx
```

### Porteira Operations

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/upload/porteira` | Upload porteira Excel file for processing | Yes |
| POST | `/api/sync/porteira` | Trigger manual sync from CEMIG SGL portal | Yes |
| GET | `/api/porteira/chart` | Get chart data for visualizations | Yes |
| GET | `/api/porteira/table` | Get detailed table data | Yes |
| GET | `/api/porteira/nao-executadas-chart` | Get not-executed operations chart data | Yes |
| POST | `/api/reset/porteira` | Reset porteira database (admin only) | Yes (Admin) |

**Example Response - Porteira Chart:**
```json
{
  "labels": ["2026-02-01", "2026-02-02"],
  "executed": [45, 52],
  "not_executed": [12, 8]
}
```

### User Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/user/portal-credentials` | Get user's stored CEMIG portal credentials | Yes |
| PUT | `/api/user/portal-credentials` | Save or update portal credentials | Yes |
| DELETE | `/api/user/portal-credentials` | Delete stored portal credentials | Yes |

**Example Request - Save Credentials:**
```json
PUT /api/user/portal-credentials
{
  "username": "cemig.user",
  "password": "portal_password"
}
```

### Scheduler Management

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/scheduler/status` | Get scheduler status and next execution times | Yes |
| POST | `/api/scheduler/toggle` | Start or stop the scheduler (admin only) | Yes (Admin) |

**Example Response - Scheduler Status:**
```json
{
  "enabled": true,
  "running": true,
  "schedule": "7h - 17h",
  "interval_minutes": 60,
  "next_run_releitura": "2026-02-02T12:00:00",
  "next_run_porteira": "2026-02-02T12:00:00"
}
```

**Example Request - Toggle Scheduler:**
```json
POST /api/scheduler/toggle
{
  "action": "start"  // or "stop"
}
```

## 🔧 Environment Variables

Create a `.env` file in the `backend/` directory with the following configuration:

```ini
# Flask Configuration
FLASK_SECRET_KEY=your-secret-key-here-change-this-in-production
FLASK_ENV=development

# CEMIG SGL Portal Credentials (for automated sync)
PORTAL_USER=your_cemig_username
PORTAL_PASS=your_cemig_password

# Scheduler Configuration
SCHEDULER_ENABLED=1                    # 1 to enable, 0 to disable
SCHEDULER_START_HOUR=7                 # Start hour (0-23)
SCHEDULER_END_HOUR=17                  # End hour (0-23)
SCHEDULER_INTERVAL_MINUTES=60          # Interval in minutes
SCHEDULER_AUTO_RELEITURA=1             # Auto-download releitura (1=yes, 0=no)
SCHEDULER_AUTO_PORTEIRA=1              # Auto-download porteira (1=yes, 0=no)
SCHEDULER_USER_ID=1                    # User ID for automated operations

# Database Configuration
DATABASE_PATH=data/vigilacore.db

# Download Configuration
DOWNLOAD_PATH=data/exports
```

### Important Notes:

- **Never commit `.env` to version control** - It's already in `.gitignore`
- Change `FLASK_SECRET_KEY` to a secure random string in production
- The `SCHEDULER_USER_ID` should be the ID of an admin user
- Scheduler will only run between `START_HOUR` and `END_HOUR`
- See [GUIA_SCHEDULER_AUTOMATICO.md](GUIA_SCHEDULER_AUTOMATICO.md) for detailed scheduler configuration

## 🔒 Security Guide

### Authentication & Authorization

- **Password Security**: All passwords are hashed using industry-standard bcrypt with salt
- **Session Management**: Secure session cookies with HTTP-only flag enabled
- **Role-Based Access Control (RBAC)**: Admin and user roles with different permission levels
- **SQL Injection Prevention**: All database queries use parameterized statements

### Best Practices

1. **Strong Passwords**: Enforce strong password policies for all users
2. **Credential Storage**: Portal credentials are encrypted in the database
3. **Environment Variables**: Never hardcode credentials - always use `.env` file
4. **HTTPS in Production**: Always use HTTPS when deploying to production
5. **Regular Updates**: Keep all dependencies updated for security patches
6. **Access Logging**: All admin operations are logged for audit trails
7. **Database Backups**: Regularly backup the SQLite database file

### Deployment Security Checklist

- [ ] Change default `FLASK_SECRET_KEY` to a strong random value
- [ ] Enable HTTPS with valid SSL certificate
- [ ] Set `FLASK_ENV=production` in `.env`
- [ ] Configure firewall to restrict access to port 5000
- [ ] Set up regular automated backups of database
- [ ] Review and limit admin user accounts
- [ ] Monitor application logs for suspicious activity
- [ ] Keep Python and all dependencies updated

## 🛠️ Tech Stack

### Backend
- **Framework**: Flask 2.x - Lightweight Python web framework
- **WSGI Server**: Werkzeug - Development server (use Gunicorn for production)
- **Database**: SQLite3 - Embedded relational database
- **Authentication**: Flask sessions with bcrypt password hashing
- **Data Processing**: Pandas, OpenPyXL, xlrd - Excel file parsing and analysis
- **Task Scheduler**: APScheduler - Automated background jobs
- **Web Scraping**: Selenium, PyAutoGUI - Browser automation for portal downloads

### Frontend
- **HTML5**: Semantic markup
- **CSS3**: Modern styling with Flexbox/Grid
- **JavaScript**: Vanilla JS for interactivity
- **Charts**: Chart.js for data visualizations
- **Icons**: Font Awesome for UI icons

### DevOps & Tools
- **Version Control**: Git & GitHub
- **Environment Management**: python-dotenv
- **Testing**: Pytest (unit tests)
- **Browser Driver**: webdriver-manager - Automatic ChromeDriver management

## 🤝 Contributing

We welcome contributions from the community! Here's how you can help:

### Reporting Issues

- Use the [GitHub Issues](https://github.com/hrsallan/VigilaCore/issues) page
- Search existing issues before creating a new one
- Provide detailed information:
  - Steps to reproduce
  - Expected vs actual behavior
  - System information (OS, Python version, browser)
  - Screenshots if applicable

### Submitting Pull Requests

1. **Fork the repository** and create a new branch
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** following the code style:
   - Use meaningful variable and function names
   - Add comments for complex logic
   - Follow PEP 8 style guide for Python code
   - Test your changes thoroughly

3. **Commit your changes** with clear messages
   ```bash
   git commit -m "Add feature: description of what you added"
   ```

4. **Push to your fork** and submit a pull request
   ```bash
   git push origin feature/your-feature-name
   ```

5. **Pull Request Guidelines**:
   - Clearly describe what your PR does
   - Reference any related issues
   - Include screenshots for UI changes
   - Ensure all tests pass
   - Update documentation if needed

### Code of Conduct

- Be respectful and constructive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards other community members

## 📄 License

This project is licensed under the **VigilaCore Non-Commercial License Version 1.0**.

- ✅ **Allowed**: Use, modify, and distribute for non-commercial purposes
- ❌ **Prohibited**: Commercial use, selling, or revenue generation
- 📋 **Requirement**: Share-alike - derivative works must use the same license

For commercial licensing inquiries, please contact [hrsallan](https://github.com/hrsallan).

See the [LICENSE](LICENSE) file for full legal terms.

---

## 🔗 Related Documentation

- [🇧🇷 README em Português](README.pt-BR.md) - Complete Portuguese version
- [📖 Guia do Scheduler Automático](GUIA_SCHEDULER_AUTOMATICO.md) - Detailed scheduler configuration guide

---

<div align="center">

**Created by [Allan Silva (hrsallan)](https://github.com/hrsallan)**

Copyright © 2026 Allan Silva. All rights reserved.

</div>
