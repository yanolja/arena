---
title: Arena
emoji: ⚔️
colorFrom: red
colorTo: purple
sdk: gradio
app_file: app.py
pinned: false
---

# [Arena](https://huggingface.co/spaces/yanolja/arena)

Get Involved: [Discuss and contribute on GitHub](https://github.com/yanolja/arena)

## How to run locally

1. **Set up a virtual environment**

   Poetry will automatically create a virtual environment for your project. If you haven't installed Poetry, you can do so by following the instructions on the [Poetry website](https://python-poetry.org/docs/#installation).

1. **Activate the virtual environment**

   Use the following command to activate the virtual environment that Poetry has created:

   ```shell
   poetry shell
   ```

1. **Install dependencies**

   With the virtual environment activated, install the project dependencies:

   ```shell
   poetry install
   ```

1. **Run the app**

   Set your environment variables and run the app:

   ```shell
   GOOGLE_CLOUD_PROJECT=<your project id> \
   CREDENTIALS_PATH=<your crednetials path> \
   MODELS_SECRET=<your secret> \
   OPENAI_API_KEY=<your key> \
   ANTHROPIC_API_KEY=<your key> \
   MISTRAL_API_KEY=<your key> \
   GEMINI_API_KEY=<your key> \
   python3 app.py
   ```

   Replace the placeholders with your actual values.

   > To run the app with [auto-reloading](https://www.gradio.app/guides/developing-faster-with-reload-mode), use `gradio app.py --demo-name app` instead of `python3 app.py`.

## Handling GCP credentials for development and deployment

### Local environment

1. Store your credentials in a file on your local machine.
1. Set the `CREDENTIALS_PATH` environment variable to point to this file.
1. The application will read the credentials from this file when running locally.

### Deployment environment

1. Set the `CREDENTIALS` environment variable in your deployment platform's settings to your credentials JSON string.
2. The application will parse and use these credentials when deployed.

## License

This project is licensed under the terms of the Apache 2.0 license. See the [LICENSE](LICENSE) file for more details.

## Contributing

Before you submit any contributions, please make sure to review and agree to our [Contributor License Agreement](CLA.md).

## Code of Conduct

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before engaging with our community.
