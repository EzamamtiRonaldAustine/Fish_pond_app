from predict import predict_water_quality
import sys

try:
    print(predict_water_quality(temperature=26.0, ph=7.2, nitrite=45.0, phosphorus=0.05))
except Exception as e:
    print(e)
