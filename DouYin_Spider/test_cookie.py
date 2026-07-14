# coding=utf-8
import json, sys
sys.path.insert(0, 'C:/Users/34355/Desktop/DouYin_Spider')
from utils.common_util import load_env
from dy_apis.douyin_api import DouyinAPI

auth = load_env()
url = "https://www.douyin.com/jingxuan?modal_id=7656177522334479473"

print(f"获取视频: {url}")
result = DouyinAPI.get_work_info(auth, url)
data = result.get('aweme_detail')

if data:
    print(f"\n✅ 标题: {data.get('desc','')}")
    print(f"   作者: {data['author']['nickname']}")
    stats = data['statistics']
    print(f"   点赞: {stats['digg_count']}  评论: {stats['comment_count']}  收藏: {stats['collect_count']}  分享: {stats['share_count']}")
    topics = [t['hashtag_name'] for t in (data.get('text_extra',[]) or [])]
    print(f"   话题: {', '.join(topics)}")
    print(f"   作品类型: {'视频' if data.get('aweme_type')==0 else '图集' if data.get('aweme_type')==68 else str(data.get('aweme_type'))}")
    # 打印完整的结构化信息
    print(f"\n📦 完整信息 (精简版):")
    print(json.dumps({
        'id': data['aweme_id'],
        'desc': data.get('desc','')[:200],
        'author': data['author']['nickname'],
        'stats': data['statistics'],
        'topics': topics,
        'video_url': data['video']['play_addr']['url_list'][0] if data.get('video') else None,
        'cover': data['video']['cover']['url_list'][0] if data.get('video') else None,
        'create_time': data['create_time'],
    }, ensure_ascii=False, indent=2))
else:
    print(f"\n❌ 获取失败")
    print(json.dumps(result, ensure_ascii=False, indent=2)[:1000])
