from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import pandas as pd
from werkzeug.utils import secure_filename
from supabase import create_client, Client


app = Flask(__name__)
CORS(app)

# Initialize Supabase
# url = "https://axoxgfbdlaqmaftwqlxp.supabase.co"
# key = "sb_publishable_a9dG4W6EfKvvhvku7Ffbaw_kBp-SsJi"
url = os.environ.get("SUPABASE_URL")
# Use Service Role Key for backend operations (bulk inserts)
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

if not url or not key:
    print("⚠️ Missing Supabase Environment Variables!")
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

# --- INTEGRATIONS ---
@app.route('/')
def index():
    return "Base44 ERP API is running."
@app.route('/api/integrations/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: return jsonify({"error": "No file"}), 400
    file = request.files['file']
    filename = secure_filename(file.filename)
    filepath = os.path.join('temp_uploads', filename)
    os.makedirs('temp_uploads', exist_ok=True)
    file.save(filepath)
    return jsonify({"file_url": filepath})

@app.route('/api/integrations/extract', methods=['POST'])
def extract_data():
    file_path = request.json.get('file_url')
    try:
        df = pd.read_excel(file_path).fillna('')
        # Find all columns that are dates and convert them to simple strings and fix spaces issue
       
        for col in df.select_dtypes(include=['datetime', 'datetimetz']).columns:
            df[col] = df[col].dt.strftime('%d/%m/%Y')
        print(df.to_dict(orient='records'))
        return jsonify({"status": "success", "output": df.to_dict(orient='records')})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# --- DYNAMIC CRUD ---
@app.route('/api/<entity>', methods=['GET', 'POST'])
def handle_entity(entity):
    table = get_table(entity)
    
    if request.method == 'GET':
        try:
            # Check for sorting params (e.g., ?sort=-created_at)
            sort = request.args.get('sort', 'id')
            desc = sort.startswith('-')
            col = sort.lstrip('-')
            
            res = supabase.table(table).select("*").order(col, desc=desc).execute()
            return jsonify(res.data)
        except Exception as e:
            print(f"Error fetching {table}: {e}")
            return jsonify([])

    if request.method == 'POST':
        try:
            res = supabase.table(table).insert(request.json).execute()
            return jsonify(res.data[0] if res.data else {}), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/<entity>/bulk', methods=['POST'])
def handle_bulk(entity):
    table = get_table(entity)
    try:
        # data is expected to be a list of dicts
        res = supabase.table(table).insert(request.json).execute()
        return jsonify(res.data), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/<entity>/<id>', methods=['PATCH', 'DELETE'])
def handle_entity_id(entity, id):
    table = get_table(entity)
    if request.method == 'PATCH':
        res = supabase.table(table).update(request.json).eq("id", id).execute()
        return jsonify(res.data)
    if request.method == 'DELETE':
        supabase.table(table).delete().eq("id", id).execute()
        return jsonify({"status": "deleted"})

if __name__ == '__main__':
    app.run(port=5000)