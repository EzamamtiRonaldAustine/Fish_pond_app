from flask import Blueprint, render_template, request, current_app, flash, redirect, url_for, session
import os
import sys
import pandas as pd
import json

# Add project root to sys.path to ensure we can import the ml package
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from ml.ML.predict import Predictor
    ml_available = True
except ImportError as e:
    print(f"ML Module Import Error: {e}")
    ml_available = False

ml_bp = Blueprint('ml', __name__)

# Initialize predictor lazily
predictor = None

def get_predictor():
    global predictor
    if predictor is None and ml_available:
        try:
            predictor = Predictor()
        except Exception as e:
            print(f"Error initializing predictor: {e}")
            return None
    return predictor

@ml_bp.route('/ml-analysis', methods=['GET', 'POST'])
def ml_analysis():
    if not session.get('token'):
        flash("Please login to access the ML Analysis dashboard.", "warning")
        return redirect(url_for('pages.login_page'))

    if not ml_available:
        flash("ML Module is not available. Please check server logs.", "danger")
        return render_template('ml_analysis.html', result=None)

    result = None
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No selected file', 'danger')
            return redirect(request.url)

        if file:
            try:
                # Read the file
                if file.filename.endswith('.xlsx'):
                    df = pd.read_excel(file)
                elif file.filename.endswith('.csv'):
                    df = pd.read_csv(file)
                else:
                    flash('Invalid file format. Please upload .xlsx or .csv', 'danger')
                    return redirect(request.url)

                # Convert dataframe to list of dicts for the predictor
                data_records = df.to_dict(orient='records')

                # Get predictor and run prediction
                pred_model = get_predictor()
                if pred_model:
                    # predictions needs a list of dictionaries
                    prediction_response = pred_model.predict_with_proba(data_records)
                    
                    # Enhance result for display
                    result = {
                        'level': prediction_response.get('predicted_level', 'Unknown'),
                        'probs': prediction_response.get('probabilities', {}),
                        'recommendation': get_recommendation(prediction_response.get('predicted_level'))
                    }
                    flash('Analysis completed successfully!', 'success')
                else:
                    flash('Failed to initialize ML model.', 'danger')

            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'danger')
                print(f"Processing Error: {e}")

    return render_template('ml_analysis.html', result=result)

def get_recommendation(level):
    if level == 'Low':
        return "Water quality is good. Maintain routine monitoring."
    elif level == 'Medium':
        return "Caution: Water quality is degrading. Increase aeration and monitor ammonia levels closely."
    elif level == 'High':
        return "CRITICAL: High algae bloom risk! Reduce feeding immediately, perform partial water change, and maximize aeration."
    return "No recommendation available."
