import os
import requests
from flask import Flask, request, render_template, send_file
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.translation.text import TextTranslationClient
import pandas as pd
from io import BytesIO

load_dotenv()
azure_ai_translator_key = os.getenv("key")
azure_ai_translator_endpoint = os.getenv("endpoint")

credential = AzureKeyCredential(azure_ai_translator_key)
text_translator = TextTranslationClient(endpoint=azure_ai_translator_endpoint, credential=credential)

response = text_translator.get_supported_languages()
data = []

if response.translation is not None:
    for key, value in response.translation.items():
        data.append({'Language_Code': key, 'Language_Name': value.name, 'Native_Name': value.native_name})

df_languages = pd.DataFrame(data)
language_dict = df_languages.set_index('Language_Code')['Language_Name'].to_dict()
reverse_language_names = {v: k for k, v in language_dict.items()}

def get_language_code(language_name):
    return reverse_language_names.get(language_name)

def get_format_from_extension(source_ext):
    format_mapping = {
        '.txt': "text/plain",
        '.txv': "text/tab-separated-values",
        '.tab': "text/tab-separated-values",
        '.csv': "text/csv",
        '.html': "text/html",
        '.htm': "text/html",
        '.mthml': "message/rfc822@application/x-mimearchive@multipart/related",
        '.mthm': "message/rfc822@application/x-mimearchive@multipart/related",
        '.pptx': "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        '.xlsx': "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        '.docx': "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        '.msg': "application/vnd.ms-outlook",
        '.xlf': "application/xliff+xml",
        '.xliff': "application/xliff+xml"
    }
    return format_mapping.get(source_ext, None)

def document_translation_fn(source_document, source_lang, target_lang):
    fileformat = get_format_from_extension(os.path.splitext(source_document.filename)[1])
    
    params = {
        "sourceLanguage": source_lang,
        "targetLanguage": target_lang,
        "api-version": "2023-11-01-preview",
    }

    headers = {"Ocp-Apim-Subscription-Key": azure_ai_translator_key}
    path = "translator/document:translate"
    url = azure_ai_translator_endpoint + path

    data = {
        "document": (source_document.filename, source_document.stream.read(), fileformat)
    }

    response = requests.post(url, headers=headers, files=data, params=params)

    return response.content, response.headers['content-type']

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        
        target_language = request.form['target_language']
        source_lang = "en"  
        target_lang = get_language_code(target_language)
        
        translated_content, content_type = document_translation_fn(file, source_lang, target_lang)

        if translated_content:
            output = BytesIO(translated_content)
            output.seek(0)
            return send_file(output, as_attachment=True, download_name=f"{os.path.splitext(file.filename)[0]}_{target_language}{os.path.splitext(file.filename)[1]}", mimetype=content_type)

    return render_template('index.html', languages=sorted(language_dict.values()))

if __name__ == '__main__':
    app.run(debug=True)
