from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pandas as pd
import io
from supabase import create_client, Client

app = Flask(__name__)

# Basic CORS setup - allows your React app to talk to this API
CORS(app)

# --- SUPABASE CONFIGURATION ---
# These are automatically provided if you used the Vercel Integration
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

if not url or not key:
    print("⚠️ Warning: Supabase Environment Variables are missing!")

supabase: Client = create_client(url, key)

# Robust mapping for entities to table names
ENTITY_MAP = {
    "Client": "clients",
    "Company": "companies",
    "GST": "gsts",
    "GSTMonthlyStatus": "gst_monthly_statuses",
    "Invoice": "invoices",
    "InvoiceItem": "invoice_items",
    "PaymentTracker": "payment_trackers",
    "Sales": "sales"
}

def get_table(entity):
    return ENTITY_MAP.get(entity, entity.lower() + "s")

# --- ROUTES ---

@app.route('/')
def index():
    return "Base44 ERP API is running on Vercel."

@app.route('/api/integrations/upload', methods=['POST'])
def upload_and_extract():
    """
    In-memory file processing. 
    Vercel does not allow saving files to disk, so we use io.BytesIO.
    """
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"status": "error", "message": "Empty filename"}), 400

    try:
        # Read the file directly into memory
        file_bytes = file.read()
        file_stream = io.BytesIO(file_bytes)
        
        # Parse Excel using Pandas from the memory stream
        df = pd.read_excel(file_stream).fillna('')
        
        # Convert date columns to DD/MM/YYYY strings to avoid JSON errors
        for col in df.select_dtypes(include=['datetime', 'datetimetz']).columns:
            df[col] = df[col].dt.strftime('%d/%m/%Y')
        
        # Clean column names (remove leading/trailing spaces)
        df.columns = df.columns.str.strip()
        
        output_data = df.to_dict(orient='records')
        
        return jsonify({
            "status": "success", 
            "output": output_data,
            "count": len(output_data)
        })
        
    except Exception as e:
        print(f"Server Error: {str(e)}")
        return jsonify({"status": "error", "message": f"Processing failed: {str(e)}"}), 500

# --- DYNAMIC CRUD OPERATIONS ---

@app.route('/api/<entity>', methods=['GET', 'POST'])
def handle_entity(entity):
    table = get_table(entity)
    
    if request.method == 'GET':
        try:
            sort = request.args.get('sort', 'id')
            desc = sort.startswith('-')
            col = sort.lstrip('-')
            invoice_id = request.args.get('invoice_id')
            barcode = request.args.get('barcode')


            if(table == "payment_trackers" and barcode):
                res = supabase.table(table).select("*").eq("barcode", barcode).execute()
                return jsonify(res.data)
            if(table == "invoice_items" and invoice_id):
                res = supabase.table(table).select("*").eq("invoice_id", invoice_id).execute()
                return jsonify(res.data)
            
            res = supabase.table(table).select("*").order(col, desc=desc).execute()

            return jsonify(res.data)
        except Exception as e:
            print(f"Error fetching {table}: {e}")
            return jsonify([])

    if request.method == 'POST':
        try:
            # Insert a single record
            res = supabase.table(table).insert(request.json).execute()
            return jsonify(res.data[0] if res.data else {}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/<entity>/bulk', methods=['POST'])
def handle_bulk(entity):
    """Handles bulk inserts from the import screen"""
    table = get_table(entity)
    try:
        # request.json should be a list of dictionaries
        res = supabase.table(table).insert(request.json).execute()
        return jsonify(res.data), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/<entity>/<id>', methods=['PATCH', 'DELETE'])
def handle_entity_id(entity, id):
    table = get_table(entity)
    
    if request.method == 'PATCH':
        try:
            res = supabase.table(table).update(request.json).eq("id", id).execute()
            return jsonify(res.data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500
            
    if request.method == 'DELETE':
        try:
            supabase.table(table).delete().eq("id", id).execute()
            return jsonify({"status": "deleted"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# --- VERCEL REQUIREMENT ---
# For Vercel, the app instance is what matters, 
# but we keep this for local testing.
if __name__ == '__main__':
    app.run(port=5000, debug=True)
