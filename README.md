# Smart Switch Controller for Shabbos/Yom Tov

This script allows you to automatically turn on and off your smart switches on Shabbos and Yom Tov. It also ensures the
lights remain on throughout your wanted time period, even if the switch is turned off manually, accidentally.

## How to Configure

There are two configuration files that you need to set up before running the script: `.env` and `config.json`.

**.env**
```dotenv
# Your Kasa Account Credentials
USERNAME=test@example.com
PASSWORD=password123

# Your OpenWeatherMap API Key (Optional but recommended to save power)
OPENWEATHERMAP_API_KEY=1234567890abcdef1234567890abcdef

# Your Location Information
LOCATION=New York, NY
TIMEZONE=America/New_York
LATITUDE=40.712776
LONGITUDE=-74.005974
```

**config.json**
```json
{
  "devices": [
    {
      "name": "Bedroom", // Optional: The name of the device
      "ip": "192.168.0.186", // The IP address of the device
      "config": {
        "always_light": false, // If the light should always be on
        // Only applicable if always_light is false
        "cloud_coverage": 50, // Optional: The cloud coverage percentage to turn on the light
        "light_times": {
          "morning": 60, // Required: How long after sunrise on Shabbos/Yom Tov the light should turn off
          "night": 30 // Required: How long before nightfall on Shabbos/Yom Tov the light should turn on
        }
      }
    },
    {
      "name": "Living Room",
      "ip": "192.168.0.91",
      "config": {
        "always_light": true
      }
    }
  ],
  "light_times": {
    "erev": 60, // How long before sunset on Erev Shabbos/Yom Tov the lights should turn on
    "motzei": 60 // How long after nightfall on Motzei Shabbos/Yom Tov the lights should turn off
  },
  "sleep_time": 30, // How often the script should check the time
  "testing": false // If the script should run in testing mode (bypasses Shabbos/Yom Tov checks)
}
```

## Contributing

If you would like to contribute to this project, please fork the repository and submit a pull request. If you have any
questions or concerns, please open an issue. I tried my best to ensure all edge cases are covered, but there may be some
that I missed. If you find any, please let me know.

## License

This project is licensed under the GNU General Public License v3.0. For more information, see the `LICENSE` file.