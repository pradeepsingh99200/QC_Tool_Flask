# from flask import Flask, jsonify
# import requests
# import os

# app = Flask(__name__)

# url = "https://vision.foodvisor.io/api/1.0/en/analysis/"
# headers = {"Authorization": "Api-Key olSEx6q7.y1CtgowrTuaSeZ3HJvGIie4HRvQp6NvP"}

# @app.route('/analyze_image/<path:image_path>', methods=['POST'])
# def analyze_image(image_path):
#     try:
#         full_image_path = os.path.join("C:\\Users\\Dell\\Downloads\\food_classifier.h5\\food-101\\food-101\\images", image_path)
        
#         with open(full_image_path, "rb") as image:
#             response = requests.post(url, headers=headers, files={"image": image})
#             response.raise_for_status()  
            
#             data = response.json()  
#             return jsonify(data) 
#     except FileNotFoundError:
#         return jsonify({"error": "File not found"}), 404
#     except requests.exceptions.RequestException as e:
#         return jsonify({"error": str(e)}), 500

# if __name__ == '__main__':
#     app.run(debug=True)
