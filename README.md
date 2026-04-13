🛠️ How to use this tool (Step-by-Step Guide)
Step 1: Install Python

Download Python from the official website (python.org).

Run the installer.

⚠️ CRITICAL STEP: At the very bottom of the installation window, check the box that says "Add Python to PATH" before clicking Install.

Step 2: Install required modules

Open your computer's terminal (Press Windows Key, type cmd, and hit Enter).

Type the following command and hit Enter: pip install requests pandas

Wait a few seconds for the installation to finish.

Step 3: Get your Riot API Key

Go to theRiot Developer Portal.

Log in with your League of Legends account.

On the dashboard, check the "I'm not a robot" box and click "Regenerate API Key".

Copy this key (it looks like RGAPI-xxxx...). Note: This basic key expires every 24 hours, so you'll need to generate a new one if you use the tool again tomorrow.

Step 4: Prepare the script

Create a new folder on your Desktop.

Inside, create a new text file and paste the Python code provided above.

Save the file as riot_matchup_tracker.py (make sure it doesn't end in .txt).

Right-click the file, open it with Notepad or any text editor, and edit the CONFIGURATION section at the top:

Paste your API_KEY.

Put your GAME_NAME and TAG_LINE (without the #).

Adjust the TARGET_CHAMPION and the number of games you want to scan.

Save the file (Ctrl + S).

Step 5: Run the magic!

Open your terminal (cmd) again.

Navigate to your folder. If it's on your Desktop, type: cd Desktop/NameOfYourFolder

Run the script by typing: python riot_matchup_tracker.py

Watch the console do the work. Once it's done, a nice .csv file will appear in your folder. You can open it with Excel or Google Sheets to see all your stats perfectly translated!
