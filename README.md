# LifePulse

```
 _      _  __     _____       _          
| |    (_)/ _|   |  __ \     | |         
| |     _| |_ ___| |__) |   _| |___  ___ 
| |    | |  _/ _ \  ___/ | | | / __|/ _ \
| |____| | ||  __/ |   | |_| | \__ \  __/
|______|_|_| \___|_|    \__,_|_|___/\___|
```

## 🌱 About LifePulse

LifePulse is a simple life habit and health tracker application designed to help you monitor and understand the interplay between your daily habits and health metrics. I've created LifePulse with three main goals in mind:
- Making it **easy-to-use** and as simple as possible
- Provide a smooth user experience across all kind of devices and screen sizes, especially **smartwatches**
- Integrate with **Fitbit** to easily track health metrics such as sleep or activity

## 🚀 Getting Started

LifePulse can easily be run locally using Docker.

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/louisguichard/lifepulse.git
   cd lifepulse
   ```

2. **Build and run with Docker:**
   ```bash
   docker build -t lifepulse .
   docker run -d -p 8080:8080 lifepulse
   ```

3. **Access the Application:**
   Open your browser and navigate to `http://localhost:8080`. You should be able to use LifePulse locally!

💡 Optionally, you can update the `config.json` file to use your own events! 

Additionally, if you want to use Cloud Storage to save your data or integrate with Fitbit, update the `.env` file. Note that Fitbit integration will require you to [create your own Fitbit application](https://dev.fitbit.com/apps/new) to obtain the client ID and secret.


## ☁️ How I Use LifePulse

I've deployed **LifePulse** on **Google Cloud Run**, making it easy to access from all my devices. Since LifePulse handles sensitive health data, I chose to keep it for my **personal use only**. Although I've tried to make access to my own data secure, my current knowledge doesn't allow me to guarantee this, and therefore to handle other people's sensitive data.
