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
   OPENAI_API_KEY=<your key> python3 app.py
   ```

   Replace `<your key>` with your GCP project ID.

   > To run the app with [auto-reloading](https://www.gradio.app/guides/developing-faster-with-reload-mode), use `gradio app.py --demo-name app` instead of `python3 app.py`.
