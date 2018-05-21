import configparser
import logging
import pandas
from pandas import DataFrame
import numpy as np
import sqlite3
from sqlite3 import Error
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.cross_validation import cross_val_predict
from sklearn.metrics import classification_report
from sklearn.model_selection import cross_val_score
from script.helper.heuristic2 import *
from script.helper.balancer import *
import time
import operator
from sklearn.externals import joblib
from win32com.test.testall import output_checked_programs

if __name__ == '__main__':
    start = time.time()
    
    config = configparser.ConfigParser()
    config.read('../../config/config.cfg')
    db_filename = config['DEFAULT']['db_filename']
    rng_seed = int(config['DEFAULT']['rng_seed'])
    vectorizer = joblib.load(config['DEFAULT']['vectorizer_filename']) 
    binarizer = joblib.load(config['DEFAULT']['binarizer_filename']) 
    classifier = joblib.load(config['DEFAULT']['model_filename'])
    output_filename = config['DEFAULT']['output_filename']
    
    log_filename = '../../log/classifier_classify_target.log'    
    logging.basicConfig(handlers=[logging.FileHandler(log_filename, 'w+', 'utf-8')], level=20)
    logging.getLogger().addHandler(logging.StreamHandler())
    
    conn = sqlite3.connect(db_filename)
    try:
        sql_text = """
        SELECT t1.file_id, t1.section_id, t1.url, t1.local_readme_file, t1.heading_markdown, t1.heading_text, t2.content_text_w_o_tags, 
        t1.abstracted_heading_text || ' ' || t2.content_text_w_o_tags AS abstracted_heading_plus_content
        FROM target_section_overview t1 
        JOIN target_section_content t2 
        ON t1.file_id=t2.file_id AND t1.section_id=t2.section_id
        """
        df = pandas.read_sql_query(con=conn, sql=sql_text)
        
        heading_plus_content_corpus = df['abstracted_heading_plus_content']
        content_corpus = df['content_text_w_o_tags']
        heading_text_corpus = df['heading_text']
        url_corpus = df['url']
        
        tfidfX = vectorizer.transform(heading_plus_content_corpus)
        
        logging.info('tfidf matrix shape: ')  
        logging.info(tfidfX.shape)
        
        # Derive features from heading text and content
        logging.info('Deriving features')
        derived_features = derive_features_using_heuristics(url_corpus, heading_text_corpus, content_corpus)
                
        # logging.info('Derived features shape:')
        # logging.info(derived_features.shape)
                
        features_tfidf = pandas.DataFrame(tfidfX.todense())
        features_tfidf.columns = vectorizer.get_feature_names()
        features_combined = pandas.concat([features_tfidf, derived_features], axis=1)
        
        # logging.info('Combined features shape:')
        # logging.info(features_combined.shape)

        labels_matrix = classifier.predict(features_combined.values)
        output = df.loc[:,['file_id','section_id','local_readme_file','heading_markdown']]
        output['result_code'] = [''.join(x) for x in binarizer.inverse_transform(labels_matrix)]
        output.to_csv(output_filename, sep=',', index=False)
        end = time.time()
        runtime_in_seconds = end - start
        logging.info('Processing completed in {0}'.format(runtime_in_seconds))
    except Error as e:
        logging.exception(e)
    except Exception as e:
        logging.exception(e)
    finally:
        conn.close()