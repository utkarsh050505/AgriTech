import pandas as pd
import joblib
import numpy as np

class CropRecommender:
    """
    A class that encapsulates the full A -> B -> C crop recommendation pipeline.
    It loads the trained models and provides a method to get final recommendations.
    
    Usage:
        # 1. Instantiate the class with the model paths
        recommender = CropRecommender('path/to/model.joblib', 'path/to/encoder.joblib')
        
        # 2. Create a farmer profile dictionary
        farmer_data = {...}
        
        # 3. Get recommendations
        results = recommender.get_recommendations(farmer_data)
    """
    def __init__(self, model_path, encoder_path):
        """
        Initializes the recommender by loading the ML model and label encoder.
        
        Args:
            model_path (str): The file path to the saved joblib model.
            encoder_path (str): The file path to the saved joblib label encoder.
        """
        self.model = None
        self.label_encoder = None
        try:
            print("Initializing CropRecommender...")
            self.model = joblib.load(model_path)
            self.label_encoder = joblib.load(encoder_path)
            print("Model and encoder loaded successfully.")
        except FileNotFoundError:
            print(f"FATAL ERROR: Could not find model at '{model_path}' or encoder at '{encoder_path}'.")
        except Exception as e:
            print(f"An unexpected error occurred during model loading: {e}")

    def _get_model_a_recommendations(self, farmer_profile):
        """
        [Model A] Uses the loaded XGBoost model to predict top 5 crops.
        """
        if not self.model or not self.label_encoder:
            raise RuntimeError("Model is not loaded. Cannot make predictions.")

        profile_df = pd.DataFrame([farmer_profile])
        probabilities = self.model.predict_proba(profile_df)
        
        top_5_indices = np.argsort(probabilities[0])[-5:][::-1]
        top_5_probabilities = probabilities[0][top_5_indices]
        top_5_crops = self.label_encoder.inverse_transform(top_5_indices)
        
        return list(zip(top_5_crops, top_5_probabilities))

    def _apply_model_b_sustainability_rules(self, recommendations, farmer_profile):
        """
        [Model B] Applies rule-based filtering for soil sustainability.
        """
        harmful_crops = ['cotton', 'sugarcane', 'jute']
        soil_type = farmer_profile.get('soil_type', '').lower()
        
        sustainable_recommendations = []
        filtered_reasons = []
        
        for crop, confidence in recommendations:
            is_safe = True
            reason = ""
            crop_lower = crop.lower()
            
            if crop_lower in harmful_crops:
                is_safe = False
                reason = f"'{crop}' can be harmful to long-term soil health."
            
            if crop_lower == 'rice' and soil_type == 'sandy':
                is_safe = False
                reason = f"'{crop}' is risky on sandy soil due to poor water retention."

            if is_safe:
                sustainable_recommendations.append((crop, confidence))
            else:
                filtered_reasons.append({'crop': crop, 'reason': reason, 'filtered_by': 'Model B'})
                
        return sustainable_recommendations, filtered_reasons

    def _apply_model_c_risk_rules(self, recommendations, farmer_profile):
        """
        [Model C] Applies rule-based filtering for risk and financial goals.
        """
        final_recommendations = []
        filtered_reasons = []

        for crop, confidence in recommendations:
            is_suitable = True
            reason = ""
            crop_lower = crop.lower()

            if crop_lower in ['cotton', 'sugarcane']:
                if farmer_profile.get('land_size', 0) < 3 or farmer_profile.get('income', 0) < 100000:
                    is_suitable = False
                    reason = f"'{crop}' is a high-investment crop, which is risky for the provided land size and/or income."

            if crop_lower in ['rice', 'sugarcane']:
                if farmer_profile.get('rainfall', 0) < 800 and farmer_profile.get('irrigation', '').lower() == 'rainfed':
                    is_suitable = False
                    reason = f"'{crop}' is water-intensive and risky with low rainfall and rainfed irrigation."

            if farmer_profile.get('financial_goal', '').lower() == 'short-term':
                if crop_lower in ['millets', 'sorghum']:
                    is_suitable = False
                    reason = f"'{crop}' has lower short-term profit, which does not align with debt clearance goals."

            if is_suitable:
                final_recommendations.append({'crop': crop, 'confidence': f"{confidence:.2%}"})
            else:
                 filtered_reasons.append({'crop': crop, 'reason': reason, 'filtered_by': 'Model C'})
                
        return final_recommendations, filtered_reasons
        
    def get_recommendations(self, farmer_profile):
        """
        Runs the full A -> B -> C pipeline and returns a structured dictionary.
        
        Args:
            farmer_profile (dict): A dictionary containing the farmer's data.

        Returns:
            dict: A dictionary with final recommendations and pipeline details.
        """
        if not self.model or not self.label_encoder:
            return {"error": "Model is not loaded properly. Cannot generate recommendations."}
            
        try:
            # Model A
            model_a_recs = self._get_model_a_recommendations(farmer_profile)
            
            # Model B
            model_b_recs, filtered_b = self._apply_model_b_sustainability_rules(model_a_recs, farmer_profile)
            
            # Model C
            final_recs, filtered_c = self._apply_model_c_risk_rules(model_b_recs, farmer_profile)

            all_filtered_reasons = filtered_b + filtered_c

            response_data = {
                "final_recommendations": final_recs,
                "filtered_crops": all_filtered_reasons,
                "pipeline_summary": {
                    "model_a_output_count": len(model_a_recs),
                    "model_b_output_count": len(model_b_recs),
                    "model_c_output_count": len(final_recs)
                }
            }
            return response_data

        except Exception as e:
            return {"error": f"An error occurred during prediction: {str(e)}"}

