import os
from flask import Blueprint, render_template, abort, send_from_directory, request, session, redirect, url_for, jsonify
from app.decorators import admin_required, login_required
from app.db import db, novels_col, chapters_col
from app.services import get_novel_meta, slug_to_name, get_novel_stats, get_chapter_content

novel_bp = Blueprint('novel', __name__)

@novel_bp.route('/api/novel/<slug>/chapter/<int:num>/')
@admin_required
def api_get_chapter(slug, num):
    name = slug_to_name(slug)
    if not name:
        return jsonify({"error": "novel not found"}), 404
    chapter = get_chapter_content(name, num)
    if not chapter:
        return jsonify({"error": "chapter not found"}), 404
    # 清洗内容以便展示
    chapter['content'] = clean_content(chapter['content'])
    return jsonify(chapter)

@novel_bp.route('/')
@admin_required
def index():
    # 管理员访问根路径直接跳转到工作台
    if session.get('role') == 'admin':
        return redirect(url_for('admin.index', **request.args))
    
    filter_type = request.args.get('type')
    novels = []
    for doc in novels_col.find({}, {'_id': 0}):
        project_id = doc['project_id']
        ch_count = chapters_col.count_documents({"project_id": project_id})
        if ch_count == 0:
            continue
        stats = get_novel_stats(project_id)
        # Compatibility fields for templates
        doc['name'] = project_id
        doc['stats'] = {
            'words': stats['words'],
            'chapters': stats['count']
        }
        doc['title'] = doc.get('title', project_id)
        
        # Apply filtering
        is_long = stats['words'] > 50000
        if filter_type == 'long' and not is_long:
            continue
        if filter_type == 'short' and is_long:
            continue
            
        novels.append({
            'name': project_id,
            'meta': doc,
            'slug': doc['slug']
        })
    return render_template('index.html', novels=novels, current_type=filter_type)

@novel_bp.route('/api/upload-chapter', methods=['POST'])
@login_required
def upload_chapter():
    data = request.get_json()
    # Support both old and new field names
    novel_name = data.get('project_id') or data.get('novelName')
    chapter_num_raw = data.get('chapter') or data.get('chapterNumber')
    content = data.get('content')
    
    if not novel_name or chapter_num_raw is None or content is None:
        return {"error": "missing fields"}, 400
        
    chapter_num = int(chapter_num_raw)
    title = data.get('title', '')
    filename = data.get('filename', '')
    chapter_end_notes = data.get('chapter_end_notes') or data.get('chapterEndNotes', '')
    version = data.get('version', 'v1')
    word_count = data.get('word_count') or data.get('wordCount') or len(content.replace(' ', '').replace('\n', ''))

    # ── 自动分离章尾说明 ──
    if not chapter_end_notes:
        markers = ['【本章钩子', '【本章爽点', '【本章节奏', '【情绪浓度', '【本章字数',
                   '【本章悬念', '【本章看点', '【本章信息', '【本章伏笔', '【本章高潮',
                   '【本章坑', '【本章金句', '【本章总结']
        lines = content.split('\n')
        sep_lines = []
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            is_marker = any(stripped.startswith(m) for m in markers)
            is_empty = stripped == ''
            is_sep = stripped.startswith('---')
            if is_marker or is_empty or is_sep:
                sep_lines.insert(0, lines[i])
            else:
                break
        if sep_lines and any(stripped.startswith(m) for m in markers
                              for stripped in [s.strip() for s in sep_lines]):
            chapter_end_notes = '\n'.join(sep_lines).strip()
            content = '\n'.join(lines[:len(lines) - len(sep_lines)]).strip()
            
    chapters_col.delete_many({"project_id": novel_name, "chapter": chapter_num})
    doc = {
        "project_id": novel_name,
        "chapter": chapter_num,
        "title": title,
        "filename": filename,
        "content": content,
        "chapter_end_notes": chapter_end_notes,
        "version": version,
        "word_count": word_count,
        "status": "merged" # Default status for uploaded chapters
    }
    chapters_col.insert_one(doc)
    return {"success": True, "chapter": chapter_num, "words": word_count}


@novel_bp.route('/api/chapter/update-content', methods=['POST'])
@admin_required
def update_chapter_content():
    data = request.get_json()
    novel_name = data.get('project_id') or data.get('novelName')
    chapter_num_raw = data.get('chapter') or data.get('chapterNumber')
    content = data.get('content')

    if not novel_name or chapter_num_raw is None or content is None:
        return {"error": "missing fields"}, 400

    chapter_num = int(chapter_num_raw)
    # 计算字数（剔除HTML标签和空白符）
    import re
    text_only = re.sub('<[^<]+?>', '', content)
    word_count = len(text_only.replace(' ', '').replace('\n', '').replace('\r', ''))

    chapters_col.update_one(
        {"project_id": novel_name, "chapter": chapter_num},
        {"$set": {"content": content, "word_count": word_count}}
    )
    return {"success": True, "wordCount": word_count}


@novel_bp.route('/novel/create/')
@admin_required
def create_novel():
    return render_template('create_novel.html')


import subprocess
import json

GENRE_MAP = {
    'fantasy': '奇幻幻想', 'scifi': '科幻未来',
    'mystery': '悬疑推理', 'romance': '都市言情',
    'historical': '历史架空'
}
LENGTH_MAP = {
    'short': '短篇（5万字以内）', 'medium': '中篇（5-20万字）',
    'long': '长篇（20-100万字）', 'epic': '超长篇（100万字以上）'
}

# ── CLI 命令接口 ──

@novel_bp.route('/api/novel/cli/', methods=['GET'])
@admin_required
def api_cli_list():
    """返回所有可用 CLI 命令的列表（JSON）"""
    commands = {
        "factory": {
            "description": "小说工厂 V3 — 创作管理",
            "subcommands": {
                "new": "novel factory new '<需求描述>'",
                "continue": "novel factory continue <项目名> [章节号]",
                "status": "novel factory status <项目名>",
                "snapshot": "novel factory snapshot <项目名> <章节>",
                "validate": "novel factory validate <项目名> <章节>",
                "event": "novel factory event <项目名> <类型> <章节> [--data JSON]",
                "arc": "novel factory arc <项目名> <arc_id>",
                "refresh": "novel factory refresh <项目名>"
            }
        },
        "reconstruct": {
            "description": "Phase 0 重建 — 诊断和重建数据",
            "subcommands": {
                "diagnose": "novel reconstruct diagnose <项目名>",
                "run": "novel reconstruct run <项目名> [--module MODULE] [--dry-run]"
            }
        },
        "judge": {
            "description": "质检评审 — AI 小说质检系统",
            "subcommands": {
                "review": "novel judge review <小说名> [--chapters RANGE] [--golden] [--dimension] [--verdict-only]",
                "patch": "novel judge patch <小说名> --chapter N --issue TYPE",
                "history": "novel judge history"
            }
        },
        "refine": {
            "description": "精修分支 — 分析/重试/同步",
            "subcommands": {
                "analyze": "novel refine analyze <项目名> [--chapters RANGE] [--types TYPE] [--full] [--dry-run]",
                "status": "novel refine status <项目名>",
                "retry": "novel refine retry <小说名> [--chapters N,N] [--auto-detect]",
                "sync": "novel refine sync <小说名> --chapters RANGE [--merge] [--dry-run]"
            }
        },
        "voice": {
            "description": "对话声音精修",
            "subcommands": {
                "refine": "novel voice refine <小说名> --chapters RANGE [--dry-run] [--max-per-chapter N]",
                "retry": "novel voice retry <小说名> --chapters 12,14,15"
            }
        },
        "lore": {
            "description": "设定同步检测",
            "subcommands": {
                "scan": "novel lore scan <项目名> [--chapters RANGE]",
                "bible-diff": "novel lore bible-diff <项目名>"
            }
        },
        "state": {
            "description": "状态差异记录",
            "subcommands": {
                "diff": "novel state diff <项目名> --chapter N",
                "verify": "novel state verify <项目名> --chapter N"
            }
        },
        "audit": {
            "description": "全量审核修复",
            "subcommands": {
                "run": "novel audit <项目名> [--report-only] [--skip-steps N,N]"
            }
        },
        "validate": {
            "description": "V3 章节校验",
            "subcommands": {
                "check": "novel validate check <项目名> <章节> [--content-file PATH]"
            }
        },
        "utility": {
            "description": "工具命令",
            "subcommands": {
                "count": "novel count <file.md>",
                "init-db": "novel init-db"
            }
        }
    }
    return jsonify(commands)


@novel_bp.route('/api/novel/cli/', methods=['POST'])
@admin_required
def api_cli_execute():
    """执行 CLI 命令并返回输出"""
    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    # 支持两种模式:
    # 1) full_command: 完整命令字符串，如 "novel judge review '诡异游戏' --chapters 1-10"
    # 2) command + args 分开，如 {command: "judge", args: ["review", "诡异游戏", "--chapters", "1-10"]}
    full_command = data.get('full_command', '')
    command = data.get('command', '')
    args = data.get('args', [])

    if full_command:
        # 直接执行完整命令
        cmd_parts = full_command.split()
        executable = cmd_parts[0] if cmd_parts else 'novel'
        cmd_args = cmd_parts[1:]
    elif command:
        executable = 'novel'
        # 将 command 和 args 拼接
        if isinstance(args, list):
            cmd_args = [command] + args
        elif isinstance(args, str):
            cmd_args = [command] + args.split()
        else:
            cmd_args = [command]
    else:
        return jsonify({"error": "请提供 full_command 或 command+args"}), 400

    # 超时设置：factory new 需要 600s，其他默认 180s
    timeout = data.get('timeout', 180)
    if command == 'factory' and (args and (isinstance(args, list) and args[0] == 'new' or isinstance(args, str) and args.startswith('new'))):
        timeout = 600
    if full_command and 'factory new' in full_command:
        timeout = 600

    try:
        result = subprocess.run(
            [executable] + cmd_args,
            capture_output=True, text=True, timeout=timeout,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        return jsonify({
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": False
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"命令执行超时（{timeout}秒）",
            "timed_out": True
        })
    except FileNotFoundError:
        return jsonify({
            "success": False,
            "returncode": -2,
            "stdout": "",
            "stderr": f"可执行文件未找到: {executable}。请确认 novel CLI 已安装。",
            "timed_out": False
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "returncode": -3,
            "stdout": "",
            "stderr": f"系统错误: {str(e)}",
            "timed_out": False
        }), 500


@novel_bp.route('/novel/cli/')
@admin_required
def cli_console():
    """CLI 控制台页面"""
    return render_template('novel_cli.html')


# ── 小说级快捷操作 ──

NOVEL_ACTIONS = {
    "audit": {
        "label": "全量审核修复",
        "icon": "fact_check",
        "desc": "扫描全书一致性、角色出场、时间线、伏笔等，自动修复",
        "command": "novel audit {name}",
        "timeout": 300,
        "warning": "耗时较长，会修改章节内容"
    },
    "reconstruct-diagnose": {
        "label": "数据诊断",
        "icon": "diagnosis",
        "desc": "检查 MongoDB 数据完整性，发现缺失/异常",
        "command": "novel reconstruct diagnose {name}",
        "timeout": 120,
        "warning": None
    },
    "reconstruct-run": {
        "label": "数据修复",
        "icon": "healing",
        "desc": "重建缺失元数据、修复摘要、补全角色登场",
        "command": "novel reconstruct run {name}",
        "timeout": 600,
        "warning": "会修改数据库数据"
    },
    "judge-review": {
        "label": "质检评审",
        "icon": "rate_review",
        "desc": "AI 八维评审（情节、设定、角色、节奏等）",
        "command": "novel judge review {name}",
        "timeout": 300,
        "warning": None
    },
    "refine-analyze": {
        "label": "精修分析",
        "icon": "tune",
        "desc": "分析所有章节，标记节奏/对话/描写等问题",
        "command": "novel refine analyze {name}",
        "timeout": 300,
        "warning": None
    },
    "voice-refine": {
        "label": "对话声音精修",
        "icon": "record_voice_over",
        "desc": "批量修改对话，使角色台词声线差异化",
        "command": "novel voice refine {name} --chapters all",
        "timeout": 600,
        "warning": "会修改对白内容，建议先备份"
    },
    "lore-scan": {
        "label": "设定一致性检测",
        "icon": "search_insights",
        "desc": "扫描章节，检测与世界设定矛盾之处",
        "command": "novel lore scan {name}",
        "timeout": 300,
        "warning": None
    },
    "state-verify": {
        "label": "状态校验",
        "icon": "verified",
        "desc": "验证各章节的状态一致性",
        "command": "novel state verify {name} --chapter 1",
        "timeout": 60,
        "warning": None
    }
}


@novel_bp.route('/api/novel/<slug>/action/', methods=['POST'])
@admin_required
def novel_action(slug):
    """执行针对当前小说的操作命令"""
    name = slug_to_name(slug)
    if not name:
        return jsonify({"error": "小说未找到"}), 404

    data = request.get_json()
    if not data:
        return jsonify({"error": "请求体为空"}), 400

    action = data.get('action', '')
    params = data.get('params', {})

    if action not in NOVEL_ACTIONS:
        return jsonify({"error": f"未知操作: {action}"}), 400

    action_def = NOVEL_ACTIONS[action]
    cmd_template = action_def['command']
    timeout = data.get('timeout', action_def['timeout'])

    # 替换 {name} 为小说名
    cmd_str = cmd_template.replace('{name}', name)

    # 支持 params 中的额外参数注入
    chapter_range = params.get('chapters', '')
    if chapter_range:
        cmd_str += f" --chapters {chapter_range}"
    if params.get('dry_run'):
        cmd_str += ' --dry-run'
    if params.get('report_only'):
        cmd_str += ' --report-only'

    try:
        # 解析完整命令
        import shlex
        cmd_parts = shlex.split(cmd_str)
        result = subprocess.run(
            cmd_parts,
            capture_output=True, text=True, timeout=timeout,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        )
        return jsonify({
            "success": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "command": cmd_str,
            "action": action,
            "novel_name": name,
            "timed_out": False
        })
    except subprocess.TimeoutExpired:
        return jsonify({
            "success": False,
            "returncode": -1,
            "stdout": "",
            "stderr": f"命令执行超时（{timeout}秒）",
            "command": cmd_str,
            "timed_out": True
        })
    except FileNotFoundError:
        return jsonify({
            "success": False,
            "returncode": -2,
            "stdout": "",
            "stderr": "novel CLI 未找到，请确认已安装",
            "command": cmd_str,
            "timed_out": False
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "returncode": -3,
            "stdout": "",
            "stderr": f"系统错误: {str(e)}",
            "command": cmd_str,
            "timed_out": False
        }), 500


@novel_bp.route('/api/novel/<slug>/actions/')
@admin_required
def list_novel_actions(slug):
    """返回当前小说可用的操作列表（含配置描述）"""
    name = slug_to_name(slug)
    if not name:
        return jsonify({"error": "小说未找到"}), 404
    return jsonify({
        "novel_name": name,
        "slug": slug,
        "actions": NOVEL_ACTIONS
    })


# ── 创建小说 ──

@novel_bp.route('/api/novel/create/', methods=['POST'])
@admin_required
def api_create_novel():
    data = request.get_json()
    title = data.get('title', '').strip()
    genre = data.get('genre', '')
    target = data.get('target', '')
    tags = data.get('tags', [])
    summary = data.get('summary', '')

    if not title:
        return jsonify({'error': '请填写作品名称'}), 400
    if not genre:
        return jsonify({'error': '请选择主要体裁'}), 400
    if not target:
        return jsonify({'error': '请选择预计字数'}), 400

    req_parts = [f"书名：{title}"]
    if genre in GENRE_MAP:
        req_parts.append(f"体裁：{GENRE_MAP[genre]}")
    if target in LENGTH_MAP:
        req_parts.append(f"篇幅：{LENGTH_MAP[target]}")
    if tags:
        req_parts.append(f"标签：{'、'.join(tags)}")
    if summary:
        req_parts.append(f"核心冲突：{summary}")

    req_text = '，'.join(req_parts)

    try:
        result = subprocess.run(
            ['novel-factory', 'new', req_text],
            capture_output=True, text=True, timeout=600,
            cwd=os.path.dirname(os.path.dirname(__file__))
        )
        if result.returncode != 0:
            return jsonify({'error': f'创建失败', 'detail': result.stderr or result.stdout}), 500
        return jsonify({
            'success': True,
            'message': f'小说「{title}」创建成功，可前往工作台查看',
            'output': result.stdout
        })
    except subprocess.TimeoutExpired:
        return jsonify({'error': '创建超时（10分钟仍未完成），请稍后在工作台查看是否已创建'}), 504
    except Exception as e:
        return jsonify({'error': f'系统错误: {str(e)}'}), 500

@novel_bp.route('/novel/<slug>/')
@admin_required
def novel_detail(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    stats = get_novel_stats(name)
    meta['stats']['words'] = stats['words']
    meta['stats']['chapters'] = stats['count']
    return render_template('novel.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/chapters/')
@admin_required
def chapter_list(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    stats = get_novel_stats(name)
    meta['stats']['words'] = stats['words']
    meta['stats']['chapters'] = stats['count']
    return render_template('chapters.html', novel_name=name, meta=meta,
                           chapters=stats['chapters'], slug=slug)

def clean_content(content):
    """去除正文头部和结尾的章节说明/勾子等标记"""
    if not content:
        return ""
    markers = ['【本章钩子', '【本章爽点', '【本章节奏', '【情绪浓度', '【本章字数',
               '【本章悬念', '【本章看点', '【本章信息', '【本章伏笔', '【本章高潮',
               '【本章坑', '【本章金句', '【本章总结']
    lines = content.split('\n')
    
    # 清理结尾
    while lines:
        stripped = lines[-1].strip()
        if not stripped or stripped.startswith('---') or any(stripped.startswith(m) for m in markers):
            lines.pop()
        else:
            break
            
    # 清理头部
    start_idx = 0
    while start_idx < len(lines):
        stripped = lines[start_idx].strip()
        if not stripped or stripped.startswith('---') or any(stripped.startswith(m) for m in markers):
            start_idx += 1
        else:
            break
            
    return '\n'.join(lines[start_idx:]).strip()


@novel_bp.route('/novel/<slug>/chapter/<int:num>/')
@admin_required
def chapter_read(slug, num):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)

    stats = get_novel_stats(name)
    target = get_chapter_content(name, num)
    if not target:
        abort(404)
    
    # 清洗正文显示，去除冗余的章节说明
    target['content'] = clean_content(target['content'])

    chapter_data_list = stats['chapters']
    idx = next(i for i, c in enumerate(chapter_data_list) if c['num'] == num)
    prev_ch = chapter_data_list[idx - 1] if idx > 0 else None
    next_ch = chapter_data_list[idx + 1] if idx < len(chapter_data_list) - 1 else None

    return render_template('chapter.html', novel_name=name, meta=meta,
                          chapter=target, prev=prev_ch, next=next_ch, slug=slug)

@novel_bp.route('/novel/<slug>/chapter/<int:num>/edit/')
@admin_required
def chapter_edit(slug, num):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    chapter = get_chapter_content(name, num)
    # If chapter doesn't exist, we can create a blank one or handle error
    if not chapter:
        chapter = {'num': num, 'title': f'第{num}章', 'content': ''}
    
    return render_template('chapter_edit.html', slug=slug, meta=meta, chapter=chapter)

@novel_bp.route('/novel/<slug>/characters/')
@admin_required
def characters(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('characters.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/world/')
@admin_required
def world_settings(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('world.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/power-system/')
@admin_required
def power_system(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('power_system.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/timeline/')
@admin_required
def timeline(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    return render_template('timeline.html', novel_name=name, meta=meta, slug=slug)

@novel_bp.route('/novel/<slug>/data/')
@admin_required
def data_center(slug):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    
    # 定义要展示的集合及其分类
    groups = [
        {
            "title": "剧情规划",
            "collections": [
                {"name": "arcs", "label": "故事卷章 (Arcs)", "icon": "Account_Tree"},
                {"name": "arc_plans", "label": "大纲规划 (Plans)", "icon": "Schema"},
                {"name": "foreshadow", "label": "伏笔埋设 (Foreshadow)", "icon": "Hiking"},
                {"name": "foreshadow_queue", "label": "伏笔队列", "icon": "Format_List_Numbered"},
                {"name": "drafts", "label": "章节草稿", "icon": "Description"}
            ]
        },
        {
            "title": "质量与评审",
            "collections": [
                {"name": "review_reports", "label": "评审报告 (Review)", "icon": "Rate_Review"},
                {"name": "refinement_log", "label": "精修记录", "icon": "Tune"},
                {"name": "refinement_patches", "label": "精修补丁", "icon": "Build"},
                {"name": "anti_repetition", "label": "防重复检测", "icon": "Repeat"},
                {"name": "legacy_reports", "label": "历史报告", "icon": "History"}
            ]
        },
        {
            "title": "状态与世界",
            "collections": [
                {"name": "world_state", "label": "动态世界状态", "icon": "Language"},
                {"name": "character_states", "label": "角色当前状态", "icon": "Recent_Actors"},
                {"name": "canonical_bible", "label": "正典设定集", "icon": "Auto_Stories"},
                {"name": "snapshot_store", "label": "项目快照 (Snapshots)", "icon": "Camera"}
            ]
        },
        {
            "title": "运行日志",
            "collections": [
                {"name": "event_log", "label": "系统执行日志", "icon": "Terminal"},
                {"name": "event_counters", "label": "计数器统计", "icon": "Functions"},
                {"name": "anti_fatigue", "label": "防疲劳系统数据", "icon": "Bedtime"}
            ]
        }
    ]
    
    return render_template('data_center.html', slug=slug, meta=meta, groups=groups)

@novel_bp.route('/novel/<slug>/data/<coll_name>/')
@admin_required
def collection_view(slug, coll_name):
    name = slug_to_name(slug)
    if not name:
        abort(404)
    meta = get_novel_meta(name)
    if not meta:
        abort(404)
    
    # 限制只能查看允许的集合
    allowed_colls = [
        'arcs', 'arc_plans', 'foreshadow', 'foreshadow_queue', 'drafts',
        'review_reports', 'refinement_log', 'refinement_patches', 'anti_repetition', 'legacy_reports',
        'world_state', 'character_states', 'canonical_bible', 'snapshot_store',
        'event_log', 'event_counters', 'anti_fatigue'
    ]
    
    if coll_name not in allowed_colls:
        abort(403)
        
    # 获取数据，根据 project_id 过滤
    coll = db[coll_name]
    raw_data = list(coll.find({"project_id": name}).sort("_id", -1).limit(100))
    
    # 递归处理数据以便 JSON 展示 (处理 ObjectId 和 datetime)
    def json_serializable(obj):
        if isinstance(obj, list):
            return [json_serializable(item) for item in obj]
        if isinstance(obj, dict):
            return {k: json_serializable(v) for k, v in obj.items()}
        if hasattr(obj, '__str__') and 'ObjectId' in str(type(obj)):
            return str(obj)
        if hasattr(obj, 'isoformat'):
            return obj.isoformat()
        return obj

    data = json_serializable(raw_data)
            
    return render_template('collection_view.html', slug=slug, meta=meta, 
                           coll_name=coll_name, data=data)

@novel_bp.route('/downloads/')
@admin_required
def download_index():
    files = []
    # Note: /root/NovelStudio might not exist on the current OS or environment.
    # We should probably make this configurable.
    base_path = '/root/NovelStudio'
    if os.path.exists(base_path):
        for f in os.listdir(base_path):
            if (f.endswith('.md') or f.endswith('.tar.gz')) and os.path.isfile(os.path.join(base_path, f)):
                size = os.path.getsize(os.path.join(base_path, f))
                files.append({'name': f, 'size': size})
    files.sort(key=lambda x: x['name'])
    return render_template('downloads.html', files=files)

@novel_bp.route('/download/<filename>')
@admin_required
def download_file(filename):
    return send_from_directory('/root/NovelStudio', filename, as_attachment=True)
