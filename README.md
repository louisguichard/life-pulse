```
 _      _  __     _____       _          
| |    (_)/ _|   |  __ \     | |         
| |     _| |_ ___| |__) |   _| |___  ___ 
| |    | |  _/ _ \  ___/ | | | / __|/ _ \
| |____| | ||  __/ |   | |_| | \__ \  __/
|______|_|_| \___|_|    \__,_|_|___/\___|
```

LifePulse is a life habit and health tracker application that integrates with Fitbit to monitor mood, daily events, health condition, activity, sleep, heart rate, and weight. 

## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/yourusername/lifepulse.git
   cd lifepulse
   ```

2. **Set Up Environment Variables:**
   Create a `.env` file in the root directory and add the following:
   ```env
    APP_ENV=production # or 'local' for development
   APP_SECRET_KEY=your_flask_app_secret_key
   FITBIT_CLIENT_ID=your_fitbit_client_id
   FITBIT_CLIENT_SECRET=your_fitbit_client_secret
   PASSWORD=your_login_password
   ```

3. **Build and Run with Docker:**
   ```bash
   docker build -t lifepulse .
   docker run -d -p 8080:8080 --env-file .env lifepulse
   ```

4. **Access the Application:**
   Open your browser and navigate to `http://localhost:8080`.