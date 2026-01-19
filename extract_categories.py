import json

# メタデータファイルを読み込み
with open('metadata_0004019324.json', 'r', encoding='utf-8') as f:
    metadata = json.load(f)

class_objs = metadata['GET_META_INFO']['METADATA_INF']['CLASS_INF']['CLASS_OBJ']

# 出力ファイルを作成
with open('dataset_0004019324_categories_complete.md', 'w', encoding='utf-8') as f:
    f.write('# データセット 0004019324 - 全カテゴリとコード一覧\n\n')
    f.write('## 基本情報\n')
    f.write('- **データセットID**: 0004019324\n')
    f.write('- **統計名**: 国勢調査\n')
    f.write('- **調査年**: 2020年\n')
    f.write('- **総レコード数**: 792,672件\n\n')
    
    for obj in class_objs:
        cat_id = obj['@id']
        cat_name = obj['@name']
        
        f.write(f'## {cat_id}: {cat_name}\n\n')
        
        classes = obj['CLASS']
        if isinstance(classes, dict):
            classes = [classes]
        
        f.write(f'**カテゴリ数**: {len(classes)}\n\n')
        f.write('| コード | 名称 | レベル | 親コード | 単位 |\n')
        f.write('|--------|------|--------|----------|------|\n')
        
        for cls in classes:
            code = cls.get('@code', '')
            name = cls.get('@name', '')
            level = cls.get('@level', '')
            parent = cls.get('@parentCode', '')
            unit = cls.get('@unit', '')
            
            f.write(f'| {code} | {name} | {level} | {parent} | {unit} |\n')
        
        f.write('\n')

print('カテゴリ一覧を dataset_0004019324_categories_complete.md に出力しました')
