# -*- coding: utf-8 -*-
import os
import logging

def setup_logger(name="AutoCutViral"):
    """
    配置日志记录器 (Configure Logger)
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        
        # Console Handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        logger.addHandler(ch)
    
    return logger

def check_directory(path):
    """
    检查目录是否存在，不存在则创建 (Check if directory exists, create if not)
    """
    if not os.path.exists(path):
        os.makedirs(path)
        return False
    return True

def get_files_with_extensions(directory, extensions=['.mp4', '.mov', '.png', '.jpg']):
    """
    获取指定目录下匹配扩展名的文件 (Get files with matching extensions in directory)
    """
    if not os.path.exists(directory):
        return []
    
    files = []
    for f in os.listdir(directory):
        if any(f.lower().endswith(ext) for ext in extensions):
            files.append(os.path.join(directory, f))
    return files
