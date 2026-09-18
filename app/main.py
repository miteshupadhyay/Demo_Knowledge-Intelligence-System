from models.vector_store import VectorStore
from services.storage_service import S3Storage
from services.llm_service import LLMService
from config import Config
import os
from langchain.document_loaders import TextLoader, PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
import tempfile
import logging
from flask import Flask, request, render_template, jsonify


app = Flask(__name__)

vectore_store= VectorStore(Config.VECTOR_DB_PATH)
storage_service = S3Storage()
llm_service = LLMService(vectore_store)

@app.route('/')
def index():
    return render_template('index.html')

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.route('/upload', methods = ['POST'])
def upload_document():
    try:
        logger.info("Upload Endpoint called")

        if 'file' not in request.files:
            logger.warning("No file in request")
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename=='':
            logger.warning("Empty Filename")
            return jsonify({'error': 'No File Selected'}), 400

        # Check File Extension
        if not file.filename.endswith(('.txt','.pdf')):
            logger.warning({'error':'Only .txt and .pdf files are supported'}), 400

        logger.debug(f"Processing file : {file.filename}")

        # Process the document
        try:
            text_chunks = process_documents(file)
            logger.debug(f"Document Processed into {len(text_chunks)} chunks")
        except Exception as e:
            logger.error(f"Error Processing document : {str(e)}")
            return jsonify({'error': f'Error Processing the document : {str(e)}'}), 500

        # Upload to S3
        try:
            file.seek(0) # Reset File Pointer
            storage_service.upload_file(file, file.filename)
            logger.debug(f"file {file.filename} Uploaded to S3 Bucket {Config.AWS_BUCKET_NAME}")
        except Exception as e:
            logger.error(f"Error uploading the file to S3:  {str(e)}")
            return jsonify({'error': f'Error uploading to S3: {str(e)}'}), 500

        # Add to Vector Store
        try:
            vectore_store.add_documents(text_chunks)
            logger.debug("Documents added to Vector Store")
        except Exception as e:
            logger.error(f"Error adding to vector store: {str(e)}")
            return jsonify({'error':f"Error Adding to vecto Store : {str(e)}"}), 500

        return jsonify({
            'message': f'File {file.filename} is uplaoded and processed successfully',
            'chunks_proceesed': len(text_chunks)
        })

    except Exception as e:
        logger.error(f"Unexpected error : {str(e)}")
        return jsonify({'error':f'Unexpected error : {str(e)}'}), 500


def query():
    


def process_documents(file):
    """Process document based on file type and return text chunks"""
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)

    try:
        # Save File Directory
        file.save(temp_path)

        # Process based on file Type
        if file.filename.endswith('.pdf'):
            loader = PyPDFLoader(temp_path)
            documents = loader.load()
        elif file.filename.endswith('.txt'):
            loader = TextLoader(temp_path)
            documents = loader.load()
        else:
            raise ValueError("Unsupported File Type")

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size = 1000,
            chunk_overlap = 200
        )

        text_chunks = text_splitter.split_documents(documents)

        return text_chunks
    finally:
    # Clean up the temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
        os.rmdir(temp_dir)


if __name__=='__main__':
    app.run(host='0.0.0.0',port=8080, debug=True)