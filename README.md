# Arena

## How to run locally

1. **Set up a virtual environment**

   Before installing dependencies, it's recommended to create a virtual environment.

1. **Install dependencies**

   With the virtual environment activated, install the project dependencies:

   ```shell
   pip install -r requirements.txt
   ```

1. **Run the app**

   Set your OpenAI API key as an environment variable and start the application:

   ```shell
   GCP_PROJECT_ID=<your project id> OPENAI_API_KEY=<your key> python3 app.py
   ```

   Replace <your project id> and <your key> with your GCP project ID and OpenAI API key respectively.
