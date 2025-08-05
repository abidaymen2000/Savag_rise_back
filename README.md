python -m venv env
.\env\Scripts\Activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
