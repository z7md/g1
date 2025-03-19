from django.http import JsonResponse
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from PyPDF2 import PdfReader
from deep_translator import GoogleTranslator
import os
from openai import OpenAI
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import json


def index(request):
    return render(request, 'bookmodule/index.html')

client = OpenAI(api_key="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", base_url="https://openrouter.ai/api/v1")
def split_text(text, max_length=5000):
    """Splits text into smaller chunks within the character limit."""
    chunks = []
    while len(text) > max_length:
        split_index = text.rfind(" ", 0, max_length)  # Split at the last space before the limit
        if split_index == -1:
            split_index = max_length  # Force split if no space found
        chunks.append(text[:split_index])
        text = text[split_index:]
    chunks.append(text)  # Append the remaining part
    return chunks

def translate_pdf(request):
    if request.method == 'POST' and request.FILES.get('pdf'):
        # Get the uploaded PDF file
        pdf_file = request.FILES['pdf']
        
        # Save the PDF file temporarily
        fs = FileSystemStorage()
        filename = fs.save(pdf_file.name, pdf_file)
        file_path = fs.path(filename)  # Get the absolute file path

        try:
            text = ""
            with open(file_path, "rb") as file:
                pdf_reader = PdfReader(file)
                for page in pdf_reader.pages:
                    extracted_text = page.extract_text()
                    if extracted_text:  # Ensure extracted text is not None
                        text += extracted_text + "\n"

            # Ensure extracted text is available
            if not text.strip():
                return JsonResponse({'status': 'error', 'message': 'No extractable text found in the PDF'})

            # Split text into chunks of max 5000 characters
            text_chunks = split_text(text, max_length=5000)

            # Translate each chunk separately
            translator = GoogleTranslator(source='auto', target='en')
            translated_chunks = [translator.translate(chunk) for chunk in text_chunks]

            # Merge the translated chunks
            translated_text = " ".join(translated_chunks)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

        finally:
            # Ensure the file is closed and deleted
            if os.path.exists(file_path):
                os.remove(file_path)  # Delete the file after processing

        

        response = client.chat.completions.create(
            model="deepseek/deepseek-r1-zero:free",
            messages=[
                {"role": "system", "content": "You are an AI that converts study material into structured learning tasks."},
                {"role": "user", "content": f"Generate a structured study plan based on the following text. \
                Each task should have:\n\
                - 'task': A clear, concise learning task\n\
                - 'duration': Estimated time in hours to complete the task\n\
                - 'status': Always set to 'To Do'\n\
                Return the response as a JSON list of dictionaries.\n\nText:\n\n{translated_text}"}
            ],
            stream=False
        )

        print(response.choices[0].message.content)
        
        
        return JsonResponse({
            'status': 'success',
            'original_text': text,
            'translated_text': response.choices[0].message.content
        })


    return render(request, 'bookmodule/tasks.html')

def extract_text_from_pdf(pdf_path):
    """Extracts text from a PDF file."""
    text = ""
    with open(pdf_path, "rb") as file:
        pdf_reader = PdfReader(file)
        for page in pdf_reader.pages:
            extracted_text = page.extract_text()
            if extracted_text:
                text += extracted_text + "\n"
    return text.strip()

def generate_mcqs_from_text(text):
    """Calls the LLM API to generate exactly 10 structured MCQs."""
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1-zero:free",  
            messages=[
                {"role": "system", "content": "You are an AI that generates multiple-choice questions (MCQs) from text."},
                {"role": "user", "content": (
                    "Generate exactly 10 MCQs from the following text. "
                    "Return the result as a text in this format: "
                    "[{\"question\": \"...\", \"options\": [\"...\", \"...\", \"...\", \"...\"], \"answer\": \"...\"}]\n\n"
                    f"Text:\n\n{text}"
                )}
            ],
            max_tokens=1500
        )

        # ✅ Correctly extract and parse AI response
        mcqs_text = response.choices[0].message.content.strip()  # Remove extra spaces/newlines
        # mcqs_dict = json.loads(mcqs_text)  # ✅ Convert AI response into Python dictionary

        return mcqs_text
        
    except Exception as e:
        return {"error": str(e)}

    except Exception as e:
        return str(e)


def translate_pdf_to_mcqs(request):
    """Django function that extracts text from a PDF, translates it in chunks, and generates MCQs."""
    if request.method == 'POST' and request.FILES.get('pdf'):
        pdf_file = request.FILES['pdf']

        # Save the uploaded file temporarily
        fs = FileSystemStorage()
        filename = fs.save(pdf_file.name, pdf_file)
        file_path = fs.path(filename)

        try:
            # ✅ Step 1: Extract text from the PDF
            extracted_text = extract_text_from_pdf(file_path)

            if not extracted_text.strip():
                return JsonResponse({'status': 'error', 'message': 'No extractable text found in the PDF'})

            # ✅ Step 2: Split text into chunks of max 5000 characters
            text_chunks = split_text(extracted_text, max_length=5000)

            # ✅ Step 3: Translate each chunk separately
            translator = GoogleTranslator(source='auto', target='en')
            translated_chunks = [translator.translate(chunk) for chunk in text_chunks]

            # ✅ Step 4: Merge the translated chunks
            translated_text = " ".join(translated_chunks)

            # ✅ Step 5: Generate MCQs from the translated text
            mcqs = generate_mcqs_from_text(translated_text)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

        finally:
            # Delete the uploaded file after processing
            if os.path.exists(file_path):
                os.remove(file_path)

        return JsonResponse({
            'status': 'success',
            'mcqs': mcqs
        })

    return render(request, 'bookmodule/slides.html')



def generate_flashcard_from_text(text):
    """Calls the LLM API to generate exactly 10 structured MCQs."""
    try:
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1-zero:free",  
            messages=[
                {"role": "system", "content": "You are an AI that generates study flashcards from text."},
                {"role": "user", "content": (
                    "Generate exactly 10 flashcards from the following text. "
                    "Return the result as a list of dictionaries in this format: "
                    "[{\"term\": \"...\", \"definition\": \"...\"}]\n\n"
                    f"Text:\n\n{text}"
                )}
            ],
            max_tokens=1500
        )

        # ✅ Correctly extract and parse AI response
        flashcard_text = response.choices[0].message.content.strip()  # Remove extra spaces/newlines
        # mcqs_dict = json.loads(mcqs_text)  # ✅ Convert AI response into Python dictionary

        return flashcard_text
        
    except Exception as e:
        return {"error": str(e)}

    except Exception as e:
        return str(e)



def translate_pdf_to_flashcard(request):
    """Django function that extracts text from a PDF, translates it in chunks, and generates MCQs."""
    if request.method == 'POST' and request.FILES.get('pdf'):
        pdf_file = request.FILES['pdf']

        # Save the uploaded file temporarily
        fs = FileSystemStorage()
        filename = fs.save(pdf_file.name, pdf_file)
        file_path = fs.path(filename)

        try:
            # ✅ Step 1: Extract text from the PDF
            extracted_text = extract_text_from_pdf(file_path)

            if not extracted_text.strip():
                return JsonResponse({'status': 'error', 'message': 'No extractable text found in the PDF'})

            # ✅ Step 2: Split text into chunks of max 5000 characters
            text_chunks = split_text(extracted_text, max_length=5000)

            # ✅ Step 3: Translate each chunk separately
            translator = GoogleTranslator(source='auto', target='en')
            translated_chunks = [translator.translate(chunk) for chunk in text_chunks]

            # ✅ Step 4: Merge the translated chunks
            translated_text = " ".join(translated_chunks)

            # ✅ Step 5: Generate flashcard from the translated text
            mcqs = generate_flashcard_from_text(translated_text)

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)})

        finally:
            # Delete the uploaded file after processing
            if os.path.exists(file_path):
                os.remove(file_path)

        return JsonResponse({
            'status': 'success',
            'mcqs': mcqs
        })

    return render(request, 'bookmodule/flashcard.html')


