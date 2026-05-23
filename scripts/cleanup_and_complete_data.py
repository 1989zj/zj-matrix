
from app.db import db, novels_col, chapters_col
from bson.objectid import ObjectId
from datetime import datetime

def cleanup_characters():
    print("--- Cleaning up character duplicates ---")
    chars_col = db['characters']
    all_chars = list(chars_col.find({}))
    
    seen = set()
    to_delete = []
    
    for char in all_chars:
        pid = char.get('project_id')
        name = char.get('name')
        key = (pid, name)
        
        if key in seen:
            to_delete.append(char['_id'])
        else:
            seen.add(key)
            
    if to_delete:
        res = chars_col.delete_many({'_id': {'$in': to_delete}})
        print(f"Deleted {res.deleted_count} duplicate characters.")
    else:
        print("No duplicate characters found.")

def complete_novel_data():
    print("--- Completing novel standard data ---")
    novels = list(novels_col.find({}))
    
    for novel in novels:
        pid = novel['project_id']
        updates = {}
        
        # Recalculate stats
        chapters = list(chapters_col.find({'project_id': pid}, {'word_count': 1}))
        total_chapters = len(chapters)
        total_words = sum(c.get('word_count', 0) for c in chapters)
        
        if novel.get('total_chapters') != total_chapters:
            updates['total_chapters'] = total_chapters
        if novel.get('total_words') != total_words:
            updates['total_words'] = total_words
            
        # Ensure standard fields
        if 'title' not in novel:
            updates['title'] = pid
        if 'slug' not in novel:
            updates['slug'] = pid.replace('proj_', '').replace('_', '-')
        if 'genre' not in novel:
            updates['genre'] = '未分类'
        if 'synopsis' not in novel:
            updates['synopsis'] = novel.get('description', '暂无简介')
        if 'tags' not in novel:
            updates['tags'] = []
        if 'status' not in novel:
            updates['status'] = '创作中'
        if 'author' not in novel:
            updates['author'] = 'AI创作'
        if 'cover' not in novel:
            updates['cover'] = ''
            
        if updates:
            novels_col.update_one({'_id': novel['_id']}, {'$set': updates})
            print(f"Updated metadata for {novel.get('title', pid)}")

        # Ensure world_bible exists
        world_col = db['world_bible']
        if not world_col.find_one({'project_id': pid}):
            world_col.insert_one({
                'project_id': pid,
                'power_system': [],
                'factions': [],
                'forbidden_rules': [],
                'world_background': '',
                'created_at': datetime.now()
            })
            print(f"Initialized missing world_bible for {pid}")

if __name__ == '__main__':
    cleanup_characters()
    complete_novel_data()
    print("Data cleanup and completion finished.")
