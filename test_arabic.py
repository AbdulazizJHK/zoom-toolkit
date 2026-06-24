import arabic_reshaper
from bidi.algorithm import get_display

text = "مرحباً بك"
reshaped = arabic_reshaper.reshape(text)
bidi = get_display(reshaped)
print("Original:", [hex(ord(c)) for c in text])
print("Reshaped:", [hex(ord(c)) for c in reshaped])
print("Bidi:", [hex(ord(c)) for c in bidi])
print("Final string:", bidi)
