"""
PERSON, NORP (nationalities, religious and political groups),
FAC (buildings, airports etc.), ORG (organizations),
GPE (countries, cities etc.), LOC (mountain ranges, water bodies etc.),
PRODUCT (products), EVENT (event names), WORK_OF_ART (books, song titles),
LAW (legal document titles), LANGUAGE (named languages),
DATE, TIME, PERCENT, MONEY, QUANTITY, ORDINAL and CARDINAL.
"""
import json
import time
import spacy
nlp = spacy.load("de_core_news_lg")

result = dict()

with open('test.json') as f:
    data = json.load(f)

for segment in data:
    doc = nlp(segment['text'])
    for ent in doc.ents:
        label = ent.label_
        text = ent.text
        if label not in result: result[label] = dict()
        if text not in result[label]: result[label][text] = list()
        formatted_time = time.strftime('%H:%M:%S',
                                       time.gmtime(segment['start']))
        result[label][text].append(formatted_time)

with open('entities.json', 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=4)


with open('test.txt') as f:
    all_text = f.read()

result = dict()
doc = nlp(all_text)
for ent in doc.ents:
    label = ent.label_
    text = ent.text
    if label not in result: result[label] = dict()
    if text not in result[label]: result[label][text] = list()
    result[label][text].append(ent.start_char)

with open('entities_whole.json', 'w') as f:
    json.dump(result, f, ensure_ascii=False, indent=4)


#doc = nlp(excerpt)
#print(doc.text)
#for ent in doc.ents:
#    print(ent.text, ent.start_char, ent.end_char, ent.label_)
