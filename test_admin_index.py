from app.db import novels_col, chapters_col
from app.services import get_novel_stats

try:
    novels = []
    for doc in novels_col.find({}, {'_id': 0}):
        project_id = doc['project_id']
        ch_count = chapters_col.count_documents({'project_id': project_id})
        if ch_count == 0:
            continue
        stats = get_novel_stats(project_id)
        doc['name'] = project_id
        doc['stats'] = {'words': stats['words'], 'chapters': stats['count']}
        doc['title'] = doc.get('title', project_id)
        novels.append({'name': project_id, 'meta': doc, 'slug': doc['slug']})
    print(f"Success, found {len(novels)} novels")
except Exception as e:
    import traceback
    print(f"Error: {e}")
    traceback.print_exc()
