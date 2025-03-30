# SyncFlow - A Comprehensive Productivity Assistant

## Overview
SyncFlow is an Electron-based desktop application designed to be your personal productivity hub. It seamlessly integrates with Google's services to help you manage emails, calendar events, and tasks. Additionally, it provides personalized recommendations based on your browsing history.

## Features

### User Authentication
- **Google OAuth Integration**: Sign in with your Google account to access Gmail, Google Calendar, and profile information.
- **Regular Login**: Alternative login method for users without Google accounts.
- **Permission Management**: Easily view and manage permissions granted to the application.

### Email Management
- **Email Viewing**: Browse and read emails from your Gmail account.
- **Email Generation**: AI-assisted email composition based on prompts.
- **Email Analysis**: Automatic categorization and analysis of email content.
- **Draft Saving**: Save generated emails directly to Gmail drafts.

### Calendar Integration
- **Event Viewing**: See upcoming events from Google Calendar.
- **Event Creation**: Create new calendar events with AI assistance.
- **Event Syncing**: Bi-directional synchronization with Google Calendar.
- **Local Event Storage**: Store events locally when offline.

### Browsing History Recommendations
- **Website Recommendations**: Get personalized website recommendations based on browsing history.
- **Category-Based Organization**: View recommendations organized by categories like Technology, News, Entertainment, etc.
- **Confidence Scoring**: Each recommendation comes with a confidence score.
- **Click Tracking**: Track which recommendations you use.

### AI Assistant
- **Email Helper**: AI-assisted email composition.
- **Reply Generator**: Generate context-aware replies to emails.
- **Browser Insights**: Get personalized recommendations and insights about your browsing habits.
- **Calendar Assistant**: AI-powered event scheduling and management.

### Security Features
- **AES-GCM Encryption**: Sensitive data stored in databases is encrypted using AES-GCM.
- **Secure Token Storage**: OAuth tokens are securely stored.
- **Permission Control**: Granular permission management for Google services.

### Activity Tracking
- **Dashboard**: View recent activities across the application.
- **Activity Types**: Track different types of activities (email, calendar, recommendations).
- **System Activities**: Monitor system-level events.

## Technical Architecture

### Frontend
- **Electron**: Cross-platform desktop application framework.
- **HTML/CSS/JavaScript**: UI components and interaction.
- **Tailwind CSS**: Styling framework.

### Backend
- **Node.js**: Main application logic and database interactions.
- **Python**: Email analysis, recommendation engine, and AI features.
- **SQLite**: Local database storage for history, emails, and activities.

### Encryption
- **AES-GCM**: Advanced encryption for sensitive data.
- **Database Protection**: Encrypted databases for history, emails, and email analysis.

### External Services
- **Google OAuth**: Authentication and API access.
- **Gmail API**: Email functionality.
- **Google Calendar API**: Calendar integration.
- **Google User Info API**: Profile information.

## Data Storage
- `history.db`: Stores browsing history and recommendations.
- `emails2.db`: Stores email data.
- `email_analysis.db`: Stores analysis results for emails.
- `activity.db`: Tracks user activities within the application.
- `creds.json`: Stores authentication credentials.

## Getting Started

### Clone the Repository
```sh
git clone https://github.com/AryanMishra1789/SyncFlow.git
cd syncflow
```

### Installation
```sh
npm install
```

### Run the Application
```sh
npm start
```

### Usage
1. Sign in with your Google account or use regular login.
2. Grant permissions to access Gmail and Calendar.
3. Start exploring the features!

## Contributing
Contributions are welcome! Please follow the standard guidelines for submitting issues and pull requests.

## License
This project is licensed under the MIT License. See the [LICENSE](https://github.com/AryanMishra1789/SyncFlow/blob/main/LICENSE) file for more details.

---

