repository 1: `git@github.com:ssriblo/telegrambot_langchain_grok.git`

repository 2: `https://github.com/gskriblo/gyumri_guide_bot`
```
python -m venv .venv
source .venv/bin/activate
pip install aiogram langchain-community langchain-openai langchain_groq

Warp conversations and updates:
`https://app.warp.dev/session/912e6a3e-48e5-4801-a5eb-ae81ce4bfc99`

run:
python main.py DEEPSEEK INFO  # Использовать DeepSeek, логи обрезать до INFO
python main.py GROQ           # Использовать Groq (по умолчанию), все логи (DEBUG по умолчанию)
python main.py NONE           # Использовать Groq (по умолчанию), логирование выключено 
python main.py                # Использовать Groq (по умолчанию), все логи (DEBUG по умолчанию)


Windows run:
Power Shell:
venv Windows:
python -m venv .venv
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
. \.venv\Scripts\Activate.ps1
