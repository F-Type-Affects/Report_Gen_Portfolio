# SML Reports Generation Application

## ⚠️ Important Note for Reviewers

The functionality of this web application is deeply integrated with proprietary project and client information on the BQE Core Platform along with personably identifiable information of the companies employees. I have sanatized the code base of this information so none of the application will not work. I am working on updating this version to use dummy data and services when convient but this is mainly to verify projects listed on my CV. While I did utalize generative A.I on this project I am the sole developer on the project which includes configuring the server enviornment.

## Overview
The SML Report Generator is a web based application that automates the creation of various reports and documentation for any project in the company. It collects Project & Client data from the BQE Core Platform.
It combines this data with Authority Having Jurisdiction (AHJ) information collected via web scraping to create an AHJ Report for a given project. 
It also automates, via web scraping, the collection of ASCE (American Society of Civil Engineers) Hazard Data (Wind, Snow, Ice, & Seismic) in two ways:
1. Scraping the ACSE Summary Table data and appending it to the AHJ Report.
2. Scraping the full ASCE Hazard Report and saving it to the project_info/ASCE_Hazard_Report directory.
   
It also automates, via web scraping, the generation of two different USDA Soil Reports:
1. Linear Extensability Report
2. Unified Soil Classification Report

Finally it can generate 8 different calculation package cover letters. One template is for general projects and the other seven templates are for various pool projects.

The application can also generate all of the reports for the user at once following the Unified Web Scraping Process.

The BQE Core Platform requires users to go through an OAuth2 login protocol to obtain user identity and access tokens. The user's information and tokens are stored in a SQLite Database file named token_storage.db.

To streamline user access a refresh token is requested in the OAuth2 process and stored for the user. There is a process in place that checks for the expiration of the users tokens and refreshes them in the background for the user so they don't need to do this every time they login

## Table of Contents

1. [What This Application Does](#what-this-application-does)
2. [Key Features](#key-features)
3. [How It Works](#how-it-works)
4. [Application Structure](#application-structure)
5. [Starting the Application](#starting-the-application)
6. [Security & User Data](#security--user-data)
7. [Report Types](#report-types)
8. [Troubleshooting](#troubleshooting)
9. [Technical Details for IT Support](#technical-details-for-it-support)

## What This Application Does

### Authentication Process - How You Log In

The application uses a secure OAuth2 authentication process, similar to "Sign in with Google" or "Sign in with Facebook":

1. **Initial Login**
   - Click "Login" on the home page
   - You're redirected to BQE CORE's official login page
   - Enter your regular BQE CORE username and password
   - BQE CORE verifies your credentials (the application never sees your password)
   - Upon successful login, BQE CORE sends an encrypted token back to the application
   - This token along with the minimal required user information is stored in a SQLite Database file named token_storage.db
   - So the user does not have to do this every time they use the application a refresh token is requested for every user and used to update expired tokens on behalf of the user

2. **Session Management**
   - Your login session remains active for 30 minutes
   - The application automatically refreshes your access token when needed
   - No need to re-login during active use
   - All credentials are encrypted and stored securely in a local database

3. **User Selection**
   - After login, select your email from the dropdown
   - This links your reports to your BQE CORE user account
   - Ensures proper access to your assigned projects

### Main Features and Workflows

#### 1. **Individual Report Generation**
Each report type can be generated separately based on project needs:

- **AHJ (Authority Having Jurisdiction) Report**
  - Scrapes the SunSpec AHJ Registry for current Authority & IBC code
  - Searches for local amendments using Google Search API
  - Finds municipal codes, ICC codes, and amendments
  - Creates an Excel workbook with Project, Client, &  Jurisdiction information
  - Includes clickable links to all found documents and web links
  - ASCE Summary data is also saved to the excel workbook created by this process

- **ASCE Hazard Reports (Two Options)**
  - **Full Report**: Downloads complete PDF from ASCE Hazard Tool
  - **Summary Report**: Extracts key values into Excel format
  - Requires: Project address, risk category, soil classification
  - Provides: Wind speeds, seismic parameters, ice/snow loads

- **USDA Soil Survey Reports**
  - Automatically navigates to Web Soil Survey
  - Generates two specialized reports:
    - Linear Extensibility Report (soil expansion/contraction)
    - Unified Soil Classification Report
  - Downloads as PDF documents

- **Cover Letter Generation**
  - 8 different templates available
  - Automatically fills in project/client information
  - Supports both general structural and pool-specific projects
  - Maintains engineer initials and license information

#### 2. **Unified Report Generation - "Generate All Reports"**
Generates all reports in one automated sequence:

**Prerequisites**: 
- AHJ Report must exist for the project (run this first if needed)
- Project must have a complete address

**Process Flow**:
1. System validates all requirements
2. Launches background process with real-time progress tracking
3. Executes in sequence:
   - ASCE Full Report PDF download
   - USDA Soil Survey reports (both types)
   - ASCE Summary data extraction
   - Updates existing AHJ Report with summary data
4. Shows progress bar with status for each step
5. Provides notifications upon completion or if errors occur

### How Data Flows Through the System

1. **Project Selection**
   - You enter a project number
   - Application queries BQE CORE API's
   - Retrieves project details, address, and client information

2. **Data Gathering**
   - Uses project address for location-based searches
   - Connects to external services (Google, ASCE, USDA)
   - Collects all required engineering data

3. **Report Generation**
   - Formats data according to SML standards
   - Applies appropriate templates
   - Performs calculations where needed

4. **File Management**
   - Automatically creates project folders if needed
   - Saves reports with standardized naming conventions
   - Pool projects go to `J:\Pools\[Project Number]\`
   - General projects go to `J:\Jobs\[Project Number]\`

### Background Processing and Progress Tracking

The application uses sophisticated background processing to handle long-running tasks:
- **Thread-based execution**: Reports generate without freezing the interface
- **Real-time updates**: Progress bars show current status
- **Server-Sent Events (SSE)**: Live communication between server and browser
- **Automatic error recovery**: Retries failed connections
- **Session tracking**: Each report generation has a unique ID for monitoring

### Integration Points

The application seamlessly integrates with:
- **BQE CORE**: Your project management system
- **Google Search API**: For building code searches
- **ASCE Hazard Tool**: For structural load calculations
- **USDA Web Soil Survey**: For geotechnical data
- **Network file system**: For report storage
- **Microsoft Office formats**: Excel and Word documents

## Key Features

### 1. **Automated Report Generation**
- Generates AHJ (Authority Having Jurisdiction) reports with building codes
- Creates ASCE hazard reports (wind, seismic, ice, and snow loads)
- Produces USDA soil survey reports
- Generates customized cover letters from templates

### 2. **BQE CORE Integration**
- Automatically pulls project information
- Retrieves client details and addresses
- Maintains billing contact information

### 3. **Real-Time Progress Tracking**
- Shows live progress bars during report generation
- Provides status updates for each step
- Notifies when reports are complete

### 4. **Template Management**
- Multiple cover letter templates for different project types
- Support for pool-specific and general structural templates
- Customizable engineer signatures and initials

## How It Works

### Step-by-Step Process

1. **Login**: Engineers log in using their BQE CORE credentials through a secure OAuth2 process
2. **Select Project**: Choose a project by entering the project number
3. **Choose Reports**: Select which reports to generate (individual or all at once)
4. **Automatic Generation**: The application:
   - Fetches project data from BQE CORE
   - Searches for building codes and amendments online
   - Scrapes ASCE hazard data for the project location
   - Retrieves soil information from USDA
   - Creates formatted reports and saves them to the network drive

## Application Structure

### Project Structure:
```
.
└── SML_Reports_Test/
    ├── Back_End/
    │   ├── app/
    │   │   ├── api/
    │   │   │   ├── routes/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── ahj_routes.py
    │   │   │   │   ├── asce_routes.py
    │   │   │   │   ├── auth_routes.py
    │   │   │   │   ├── cover_letter_routes.py
    │   │   │   │   ├── progress_routes.py
    │   │   │   │   ├── project_routes.py
    │   │   │   │   ├── soil_routes.py
    │   │   │   │   └── workflow_routes.py
    │   │   │   ├── utils/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── background_tasks.py
    │   │   │   │   ├── progress_tracking.py
    │   │   │   │   └── validation.py
    │   │   │   └── __init__.py
    │   │   ├── auth/
    │   │   │   ├── __init__.py
    │   │   │   ├── auth.py
    │   │   │   └── token_manager.py
    │   │   ├── core/
    │   │   │   ├── __init__.py
    │   │   │   ├── config.py
    │   │   │   ├── database.py
    │   │   │   └── models.py
    │   │   ├── services/
    │   │   │   ├── ahj/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── ahj_manager.py
    │   │   │   ├── asce/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── asce_config.py
    │   │   │   │   ├── asce_hazard_report.py
    │   │   │   │   └── asce_hazard_summary.py
    │   │   │   ├── project/
    │   │   │   │   ├── __init__.py
    │   │   │   │   ├── cover_letter.py
    │   │   │   │   ├── export_project_details.py
    │   │   │   │   └── project_manager.py
    │   │   │   ├── soil/
    │   │   │   │   ├── __init__.py
    │   │   │   │   └── soil_scraper.py
    │   │   │   └── __init__.py
    │   │   ├── utils/
    │   │   │   └── drivers/
    │   │   │       └── chromedriver.exe
    │   │   └── __init__.py
    │   ├── __init__.py
    │   └── server.py
    ├── Front_End_Web/
    │   ├── static/
    │   │   ├── css/
    │   │   │   ├── confirm_soil_survey.css
    │   │   │   ├── display_letter_details.css
    │   │   │   ├── display_report_details.css
    │   │   │   ├── display_summary_details.css
    │   │   │   ├── flash_message.css
    │   │   │   ├── index_styling.css
    │   │   │   ├── progress_tracking.css
    │   │   │   ├── progress-enhancements.css
    │   │   │   ├── select_asce_options.css
    │   │   │   ├── select_project_number.css
    │   │   │   └── select_user_email.css
    │   │   ├── js/
    │   │   │   └── unified-progress-tracker.js
    │   │   └── images/
    │   └── templates/
    │       ├── confirm_soil_survey.html
    │       ├── display_letter_details.html
    │       ├── display_report_details.html
    │       ├── display_summary_details.css
    │       ├── flash_message.html
    │       ├── index_styling.html
    │       ├── select_asce_options.html
    │       ├── select_project_number.html
    │       └── select_user_email.html
    ├── vir_env/
    ├── .env
    ├── .gitignore
    ├── gunicorn.log
    ├── requirements.txt
    └── __init__.py
```

### Front-End (What You See)
```
Front_End_Web/
├── templates/           # HTML pages
│   ├── index.html      # Home page
│   ├── select_project_number.html
│   ├── unified_reports_config.html
│   └── ... (other screens)
└── static/             
    ├── css/            # Visual styling (colors, layouts)
    ├── js/             # Interactive features (progress bars, buttons)
    └── images/         # Logo and graphics
```

### Back-End (The Engine)
```
Back_End/
├── server.py           # Main application launcher
├── app/
│   ├── api/routes/     # URL endpoints
│   │   ├── auth_routes.py        # Login/logout
│   │   ├── project_routes.py     # Project selection
│   │   ├── ahj_routes.py         # Scrape AHJ Registry
│   │   ├── asce_routes.py        # Hazard reports & summary data
│   │   ├── soil_routes.py        # Soil surveys
│   │   └── cover_letter_routes.py # Cover letters template 
│   │
│   ├── services/       # The workers that do the actual tasks
│   │   ├── project/    # Project & Client Data, Excel workbook creation, Cover Letter generation, Saving Documents
│   │   ├── asce/       # ASCE Scraper configuration, ASCe Summary logic, Hazard Report Logic
│   │   ├── soil/       # Soil Scraper configuration and Soil Scraper
│   │   └── google_search/ # Impliments google's programmable search engine with custom results
│   │
│   ├── auth/           # Security and login management
│   └── core/           # Database and configuration
│
└── templates/          # Document templates
    └── cover_letters/  # All cover letter templates
```

## Starting the Application

### For Daily Use (Production Server)
The application runs continuously on the company server. Simply navigate to:
```
http://server-ip
```

### For Development/Testing

#### Prerequisites - What You Need First

1. **Git** (for downloading the code from GitHub)
   - Download from: https://git-scm.com/download/win
   - Run the installer, accept all default settings

2. **Python 3.10 or newer**
   - Download from: https://www.python.org/downloads/
   - The virtual enviorenment will run version 3.12
   - **IMPORTANT**: During installation, check the box that says "Add Python to PATH"

3. **Google Chrome** (latest version)
   - The application uses Chrome to scrape websites
   - Download from: https://www.google.com/chrome/

4. **Redis for Windows**
   - Download from: https://github.com/microsoftarchive/redis/releases
   - Download the .msi installer (not the .zip file)
   - Run installer with default settings

##### 1. Clone the Repository from GitHub

Open Command Prompt (press Windows key + R, type `cmd`, press Enter) and run:

```bash
# Navigate to where you want to store the project
cd C:\Users\[YourUsername]\Desktop

# Clone (download) the repository
git clone https://github.com/[your-organization]/SML_Reports_Test.git

# Enter the project directory
cd SML_Reports_Test
```

##### 2. Create a Python Virtual Environment

```bash
# Create a new virtual environment named 'vir_env'
python -m venv vir_env

# Activate the virtual environment
# You'll see (vir_env) appear at the beginning of your command prompt
./vir_env\Scripts\activate
```

**Note**: If you get an error about execution policies, run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

##### 3. Install Required Python Packages

With the virtual environment activated, install all dependencies:

```bash
# This installs all required packages listed in requirements.txt
pip install -r requirements.txt
```

This may take a few minutes as it downloads and installs packages like:
- Flask (web framework)
- Selenium (web scraping)
- openpyxl (Excel manipulation)
- python-docx (Word document creation)

##### 4. Configure Environment Variables

The application needs a `.env` file with your credentials and settings:

1. For security the .env is not tracked via GitHub and only exist in the local directories of each branch aka on the local machine
2. If lost will have to be reimplimented
3. the config file can be used to do this

##### 5. Start Redis Server

Redis must be running for the application to work:

```bash
# Open a new Command Prompt window (keep this running)
./redis-server.exe
```

You should see Redis start up and display version information.

##### 6. Run the Application

Back in your original Command Prompt (with virtual environment activated):

```bash
# Start the Flask development server
python Back_End/server.py
```

You should see output like:
```
* Running on http://127.0.0.1:8888
* Debug mode: on
```

##### 7. Access the Application

Open your web browser and navigate to:
```
http://127.0.0.1:8888
```

You should see the SML Reports home page!

#### Common Development Commands

```bash
# Always activate virtual environment first when starting work
./vir_env\Scripts\activate

# Install a new package
pip install package_name

# Update requirements.txt after installing new packages
pip freeze > requirements.txt

# Deactivate virtual environment when done
deactivate

# Pull latest changes from GitHub
git pull origin develop

# Check which branch you're on
git branch

# Switch to develop branch
git checkout develop
```

#### Development Best Practices

1. **Always use the virtual environment** - Activate it before working
2. **Keep dependencies updated** - Run `pip install -r requirements.txt` after pulling changes
3. **Don't commit sensitive data** - Keep API keys in `.env`, never in code
4. **Test locally first** - Ensure all reports generate correctly before pushing changes
5. **Check file paths** - Development paths may differ from production

## Security & User Data

### How Your Credentials Are Stored
- **BQE CORE Login**: Uses OAuth2 (like "Sign in with Google")
- **Token Storage**: Encrypted tokens stored in a local database
- **Session Management**: 30-minute timeout for security
- **No Passwords Stored**: The application never stores your actual password

### Data Flow
1. You log in through BQE CORE's secure portal
2. BQE CORE sends back an encrypted token
3. The application uses this token to access your projects
4. Tokens automatically refresh when needed

## Report Types

### 1. AHJ Report
- **What it does**: Finds building codes and amendments for the project jurisdiction
- **Output**: Excel file with jurisdiction info, project and client data, and links to possible amendments to the code
- **Location**: Saved to `J:\Jobs\[Project Number]\Project_Info\AHJ_Report

### 2. ASCE Full Report
- **What it does**: Downloads complete ASCE hazard data PDF
- **Requirements**: Project address, risk category, soil class
- **Output**: PDF report from ASCE Hazard Tool
- **Location**: J:\Jobs\[Project Number]\Project_Info\ASCE_Hazard_Report

### 3. ASCE Summary
- **What it does**: Extracts key values (wind speed, seismic data, etc.)
- **Output**: Added as new sheet in AHJ Excel report
- **Note**: Requires AHJ report to exist first

### 4. USDA Soil Survey
- **What it does**: Retrieves soil classification and properties
- **Output**: Two PDF reports (Linear Extensibility & Unified Classification)
- **Location: J:\Jobs\[Project Number]\Project_Info\USDA_Soil_Reports

### 5. Cover Letters
- **Templates Available**:
  - General Structural Calculations
  - Pool Calculations (various standards)
  - Revision Letters
  - Supplemental Reports
- **Customization**: Automatically fills in project/client details

## Technical Details for IT Support

### System Requirements
- **Python**: 3.12.1
- **Redis**: 6.0+ (for session management)
- **Chrome**: Latest version (for web scraping)
- **Network Access**: 
  - BQE CORE API
  - Google Search API
  - ASCE Hazard Tool
  - USDA Web Soil Survey

### Environment Variables
The application requires a `.env` file with:
- BQE CORE OAuth credentials
- Google API keys
- File path configurations
- Database locations

### Dependencies
All Python packages are listed in `requirements.txt`:
- Flask (web framework)
- Selenium (web scraping)
- openpyxl (Excel manipulation)
- python-docx (Word documents)
- redis (session storage)

### Network Drives
- Reports: `J:\Jobs\` and `J:\Pools\`
- Templates: Configured in `.env` file
- Ensure service account has write access

### Monitoring
- Logs location: Check console output
- Session timeout: 30 minutes
- Background tasks: Thread-based with progress tracking

---

## Support Contact

For technical issues or questions about the application:
- **Developer**: Frank Stranathan
- **Email**: fstranathan@gmail.com

For BQE CORE access issues:
- Contact your BQE CORE administrator

For network or server issues:
- Contact IT Support

---

*Last Updated: July 2025*
*Version: 1.0 - Development Branch*
