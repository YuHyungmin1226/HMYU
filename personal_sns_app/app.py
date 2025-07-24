import streamlit as st
import os
import json
from datetime import datetime
import uuid
import hashlib
from secure_auth import SecureAuth
from session_manager import SessionManager
from enhanced_url_utils import EnhancedURLPreviewGenerator

# Supabase 연동
USE_SUPABASE = False
supabase = None

try:
    from supabase import create_client # type: ignore
    if hasattr(st, 'secrets') and 'supabase_url' in st.secrets and 'supabase_key' in st.secrets:
        supabase_url = st.secrets.supabase_url
        supabase_key = st.secrets.supabase_key
        supabase = create_client(supabase_url, supabase_key)
        USE_SUPABASE = True
    else:
        USE_SUPABASE = False
        supabase = None
except ImportError:
    USE_SUPABASE = False
    supabase = None
except Exception as e:
    USE_SUPABASE = False
    supabase = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POSTS_PATH = os.path.join(BASE_DIR, "posts.json")
USERS_PATH = os.path.join(BASE_DIR, "users.json")
SESSION_PATH = os.path.join(BASE_DIR, "session.json")

# Supabase/로컬 게시글, 사용자 함수(첨부파일 관련 부분 없음)
def supabase_load_posts():
    if not USE_SUPABASE or supabase is None:
        return []
    try:
        response = supabase.table('posts').select('*').order('created_at', desc=True).execute()
        posts_data = response.data
        
        # URL 미리보기 데이터를 JSON에서 파싱
        for post in posts_data:
            if 'url_previews' in post and isinstance(post['url_previews'], str):
                try:
                    import json
                    post['url_previews'] = json.loads(post['url_previews'])
                except:
                    post['url_previews'] = []
            elif 'url_previews' not in post:
                post['url_previews'] = []
        
        return posts_data
    except Exception as e:
        st.warning(f"Supabase 게시글 로드 실패: {e}")
        return []

def supabase_save_post(post_data):
    if not USE_SUPABASE or supabase is None:
        return False
    try:
        # URL 미리보기 데이터를 JSON 문자열로 변환
        if 'url_previews' in post_data:
            import json
            post_data_copy = post_data.copy()
            post_data_copy['url_previews'] = json.dumps(post_data['url_previews'], ensure_ascii=False)
            supabase.table('posts').insert(post_data_copy).execute()
        else:
            supabase.table('posts').insert(post_data).execute()
        return True
    except Exception as e:
        st.warning(f"Supabase 게시글 저장 실패: {e}")
        return False

def supabase_update_post(post_id, update_data):
    if not USE_SUPABASE or supabase is None:
        return False
    try:
        supabase.table('posts').update(update_data).eq('id', post_id).execute()
        return True
    except Exception as e:
        st.warning(f"Supabase 게시글 업데이트 실패: {e}")
        return False

def supabase_delete_post(post_id):
    if not USE_SUPABASE or supabase is None:
        return False
    try:
        supabase.table('posts').delete().eq('id', post_id).execute()
        return True
    except Exception as e:
        st.warning(f"Supabase 게시글 삭제 실패: {e}")
        return False

def supabase_load_users():
    if not USE_SUPABASE or supabase is None:
        return {"admin": hash_password("admin123")}
    try:
        response = supabase.table('users').select('*').execute()
        users = {}
        for user in response.data:
            users[user['username']] = user['password_hash']
        return users
    except Exception as e:
        st.warning(f"Supabase 사용자 로드 실패: {e}")
        return {"admin": hash_password("admin123")}

def supabase_save_user(username, password_hash):
    if not USE_SUPABASE or supabase is None:
        return False
    try:
        supabase.table('users').insert({
            'username': username,
            'password_hash': password_hash,
            'created_at': datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.warning(f"Supabase 사용자 저장 실패: {e}")
        return False

def supabase_update_user(username, password_hash):
    if not USE_SUPABASE or supabase is None:
        return False
    try:
        supabase.table('users').update({
            'password_hash': password_hash,
            'updated_at': datetime.now().isoformat()
        }).eq('username', username).execute()
        return True
    except Exception as e:
        st.warning(f"Supabase 사용자 업데이트 실패: {e}")
        return False

# 로컬 파일 시스템 함수들 (백업용)
def safe_load_json(path, default):
    try:
        if not os.path.exists(path) or os.path.getsize(path) == 0:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default, f, ensure_ascii=False, indent=2)
        return default

def safe_save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"파일 저장 오류: {e}")

def hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

# 보안 인증 시스템 초기화
secure_auth = SecureAuth(USERS_PATH, SESSION_PATH, use_supabase=USE_SUPABASE, supabase_client=supabase)
session_manager = SessionManager(SESSION_PATH)

# URL 미리보기 생성기 초기화
url_preview_generator = EnhancedURLPreviewGenerator()

# 세션 상태 초기화
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'current_user' not in st.session_state:
    st.session_state.current_user = None
if 'password_changed' not in st.session_state:
    st.session_state.password_changed = False

# 세션 유효성 검증
if st.session_state.session_id:
    session_data = session_manager.validate_session(st.session_state.session_id)
    if isinstance(session_data, dict):
        st.session_state.logged_in = True
        st.session_state.current_user = session_data.get("username")
        st.session_state.password_changed = session_data.get("password_changed", True)
    else:
        # 세션이 만료되었거나 유효하지 않음
        st.session_state.session_id = None
        st.session_state.logged_in = False
        st.session_state.current_user = None
        st.session_state.password_changed = False

# 데이터 로드
try:
    if USE_SUPABASE:
        posts = supabase_load_posts()
        users = supabase_load_users()
    else:
        posts = safe_load_json(POSTS_PATH, [])
        users = safe_load_json(USERS_PATH, {"admin": hash_password("admin123")})
except Exception as e:
    # 데이터 로드 실패 시 기본값 사용
    posts = []
    users = {"admin": hash_password("admin123")}

# CSS 스타일
st.markdown("""
<style>
body, .stApp, .block-container {
    background: #f5f6fa !important;
    color: #222 !important;
}

/* 카드 기본 스타일 */
.post-card-light {
    background: white !important;
    border: 1px solid #e1e8ed !important;
    color: #222 !important;
}

.post-content-light {
    color: #222 !important;
}

/* 다크모드 대응 */
@media (prefers-color-scheme: dark) {
    body, .stApp, .block-container {
        background: #181c1f !important;
        color: #f5f6fa !important;
    }
    .post-card-light {
        background: #23272b !important;
        border: 1px solid #444 !important;
        color: #f5f6fa !important;
    }
    .post-content-light {
        color: #f5f6fa !important;
    }
    .post-header, .post-author, .post-time {
        color: #90caf9 !important;
    }
    .url-preview-card, .youtube-preview-card {
        background: #23272b !important;
        border: 1px solid #444 !important;
        color: #f5f6fa !important;
    }
    .url-preview-title, .youtube-title {
        color: #fff !important;
    }
    .url-preview-description, .url-preview-site, .youtube-channel, .youtube-domain {
        color: #b0b8c1 !important;
    }
    .stTextInput>div>div>input, .stTextArea textarea {
        background: #23272b !important;
        color: #f5f6fa !important;
    }
}
.stTextInput>div>div>input, .stTextArea textarea {
    font-size: 18px;
}
.stTextInput, .stTextArea, .stButton {
    margin-bottom: 18px;
}
/* 게시글 주변 불필요한 테두리 제거 */
div[data-testid="stVerticalBlock"] > div[style*="border"] {
    border: none !important;
    background: transparent !important;
    padding: 0 !important;
}
/* 폼과 버튼 주변 테두리 제거 */
.stForm {
    border: none !important;
    background: transparent !important;
}
[data-testid="column"] {
    border: none !important;
    background: transparent !important;
}

.stButton > button {
    margin-right: 10px;
}
.button-row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 8px;
}

/* URL 미리보기 스타일 */
.url-preview-card {
    border: 1px solid #e1e8ed;
    border-radius: 14px;
    overflow: hidden;
    margin: 12px 0;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    transition: box-shadow 0.2s ease;
}
.url-preview-card:hover {
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}
.url-preview-link {
    text-decoration: none;
    color: inherit;
    display: block;
}
.url-preview-content {
    display: flex;
    min-height: 125px;
}
.url-preview-content-no-image {
    padding: 16px;
}
.url-preview-image {
    width: 125px;
    min-width: 125px;
    background: #f7f9fa;
    display: flex;
    align-items: center;
    justify-content: center;
}
.url-preview-image img {
    width: 100%;
    height: 125px;
    object-fit: cover;
}
.url-preview-text {
    padding: 16px;
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
}
.url-preview-title {
    font-weight: 600;
    font-size: 16px;
    line-height: 1.3;
    color: #14171a;
    margin-bottom: 4px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}
.url-preview-description {
    font-size: 14px;
    line-height: 1.4;
    color: #657786;
    margin-bottom: 8px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}
.url-preview-site {
    font-size: 13px;
    color: #657786;
    text-transform: uppercase;
    font-weight: 500;
}

/* YouTube 미리보기 스타일 */
.youtube-preview-card {
    border: 1px solid #e1e8ed;
    border-radius: 16px;
    overflow: hidden;
    margin: 12px 0;
    background: #ffffff;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    transition: all 0.2s ease;
    max-width: 500px;
}
.youtube-preview-card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    transform: translateY(-2px);
}
.youtube-preview-link {
    text-decoration: none;
    color: inherit;
    display: block;
}
.youtube-thumbnail-container {
    position: relative;
    width: 100%;
    height: 280px;
    background: #000;
    overflow: hidden;
}
.youtube-thumbnail {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
}
.youtube-play-button {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    opacity: 0.8;
    transition: opacity 0.2s ease;
}
.youtube-preview-card:hover .youtube-play-button {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1.1);
}
.youtube-info {
    padding: 16px;
}
.youtube-title {
    font-weight: 600;
    font-size: 16px;
    line-height: 1.4;
    color: #0f0f0f;
    margin-bottom: 8px;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
}
.youtube-channel {
    font-size: 14px;
    color: #606060;
    margin-bottom: 4px;
    font-weight: 500;
}
.youtube-domain {
    font-size: 12px;
    color: #909090;
    text-transform: uppercase;
    font-weight: 500;
    letter-spacing: 0.5px;
}

/* 반응형 디자인 */
@media (max-width: 600px) {
    .url-preview-content {
        flex-direction: column;
    }
    .url-preview-image {
        width: 100%;
        min-width: auto;
        height: 200px;
    }
    .url-preview-image img {
        height: 200px;
    }
    .youtube-preview-card {
        max-width: 100%;
    }
    .youtube-thumbnail-container {
        height: 220px;
    }
    /* 모바일에서 첨부된 미디어 크기 최적화 */
    .post-card-light {
        padding: 16px !important;
        margin-bottom: 16px !important;
    }
}

/* 첨부된 미디어의 최대 높이 제한 (모든 화면 크기) */
.post-card-light img {
    max-height: 400px !important;
    width: 100% !important;
    object-fit: contain !important;
}

.post-card-light video {
    max-height: 300px !important;
    width: 100% !important;
    object-fit: contain !important;
}

@media (max-width: 768px) {
    .post-card-light img {
        max-height: 250px !important;
    }
    .post-card-light video {
        max-height: 200px !important;
    }
}

@media (max-width: 480px) {
    .post-card-light img {
        max-height: 200px !important;
    }
    .post-card-light video {
        max-height: 150px !important;
    }
}
</style>
""", unsafe_allow_html=True)

try:
    if not st.session_state.logged_in:
        # 중복 타이틀 제거, 좌측 정렬 컨테이너 적용
        with st.container():
            st.markdown('<div style="margin-top:40px; margin-bottom:32px; text-align:left;"><span style="font-size:38px; font-weight:700; letter-spacing:-2px;">로그인</span></div>', unsafe_allow_html=True)
            auth_mode = st.radio(" ", ["로그인", "회원가입"], index=0, horizontal=True, label_visibility="collapsed")
            if auth_mode == "회원가입":
                # 회원가입 텍스트(섹션 타이틀) 제거
                with st.form("signup_form"):
                    new_username = st.text_input("사용자명", key="signup_username")
                    new_password = st.text_input("비밀번호", type="password", key="signup_password")
                    confirm_password = st.text_input("비밀번호 확인", type="password", key="signup_confirm")
                    signup_submitted = st.form_submit_button("회원가입")
                    if signup_submitted:
                        if new_password != confirm_password:
                            st.error("비밀번호가 일치하지 않습니다.")
                        else:
                            success, message = secure_auth.register_user(new_username, new_password)
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
            else:
                with st.form("login_form"):
                    username = st.text_input("사용자명", key="login_username")
                    password = st.text_input("비밀번호", type="password", key="login_password")
                    login_submitted = st.form_submit_button("로그인")
                    if login_submitted:
                        success, session_id, message = secure_auth.login(username, password)
                        if success:
                            st.session_state.session_id = session_id
                            st.session_state.logged_in = True
                            st.session_state.current_user = username
                            st.session_state.password_changed = not (username == "admin" and password == "admin123")
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
    else:
        # 비밀번호 변경이 필요한 경우 (admin 계정이 기본 비밀번호로 로그인한 경우)
        if st.session_state.current_user == "admin" and not st.session_state.password_changed:
            st.title("비밀번호 변경")
            st.warning("보안을 위해 기본 비밀번호를 변경해주세요.")
            with st.form("change_password_form"):
                current_password = st.text_input("현재 비밀번호", type="password")
                new_password = st.text_input("새 비밀번호", type="password")
                confirm_password = st.text_input("새 비밀번호 확인", type="password")
                change_submitted = st.form_submit_button("비밀번호 변경")
                if change_submitted:
                    if not current_password or not new_password or not confirm_password:
                        st.error("모든 필드를 입력해주세요.")
                    elif current_password != "admin123":
                        st.error("현재 비밀번호가 올바르지 않습니다.")
                    elif new_password != confirm_password:
                        st.error("새 비밀번호가 일치하지 않습니다.")
                    elif new_password == "admin123":
                        st.error("새 비밀번호는 기존 비밀번호와 달라야 합니다.")
                    else:
                        new_password_hash = hash_password(new_password)
                        success, message = secure_auth.change_password("admin", current_password, new_password)
                        if success:
                            st.session_state.password_changed = True
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
            if st.button("나중에 변경"):
                st.session_state.password_changed = True
                st.rerun()
        else:
            st.markdown(f"**안녕하세요, {st.session_state.current_user}님!**")
            
            # Admin 전용 사용자 관리 기능
            if st.session_state.current_user == "admin":
                st.markdown("---")
                st.subheader("🔧 관리자 기능")
                
                # 보안 정보
                st.info(f"현재 로그인된 사용자: {st.session_state.current_user}")
                st.info(f"Supabase 사용 여부: {USE_SUPABASE}")
                st.info(f"활성 세션 수: {session_manager.get_active_sessions_count()}")
                
                # 로그인 시도 정보 (관리자용)
                if st.session_state.current_user:
                    try:
                        login_info = secure_auth.get_login_attempts_info(st.session_state.current_user)
                        if isinstance(login_info, dict):
                            if login_info.get('count', 0) > 0:
                                st.warning(f"로그인 시도: {login_info['count']}회")
                            if login_info.get('locked', False):
                                st.error(f"계정 잠금: {login_info['remaining_time']}분 남음")
                    except Exception as e:
                        pass  # 로그인 정보 로드 실패시 무시
                
                # 사용자 목록 표시 (매번 새로 로드)
                if USE_SUPABASE:
                    try:
                        response = supabase.table('users').select('*').execute()
                        all_users = response.data if response.data else []
                        st.info(f"Supabase에서 로드된 사용자 수: {len(all_users)}")
                    except Exception as e:
                        st.error(f"사용자 목록 로드 오류: {e}")
                        all_users = []
                else:
                    all_users = [{"username": username, "created_at": "N/A"} for username in users.keys()]
                    st.info(f"로컬에서 로드된 사용자 수: {len(all_users)}")
                
                if all_users:
                    st.write("**등록된 사용자 목록:**")
                    for user in all_users:
                        if isinstance(user, dict) and user.get("username") != "admin":  # admin 제외
                            col1, col2, col3 = st.columns([3, 2, 1])
                            with col1:
                                st.write(f"👤 {user.get('username', 'Unknown')}")
                            with col2:
                                created_at = user.get('created_at', 'N/A')
                                if created_at and created_at != 'N/A':
                                    try:
                                        st.write(f"가입일: {created_at[:10]}")
                                    except:
                                        st.write("가입일: N/A")
                                else:
                                    st.write("가입일: N/A")
                            with col3:
                                if st.button(f"삭제", key=f"delete_user_{user.get('username', 'unknown')}", use_container_width=True):
                                    username = user.get('username', '')
                                    if username:
                                        if USE_SUPABASE:
                                            try:
                                                st.info(f"사용자 '{username}' 삭제 중...")
                                                # 해당 사용자의 게시글도 함께 삭제
                                                posts_response = supabase.table('posts').delete().eq('author', username).execute()
                                                st.info(f"게시글 {len(posts_response.data) if posts_response.data else 0}개 삭제됨")
                                                
                                                # 사용자 삭제
                                                user_response = supabase.table('users').delete().eq('username', username).execute()
                                                st.success(f"사용자 '{username}'가 삭제되었습니다.")
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"사용자 삭제 오류: {e}")
                                        else:
                                            # 로컬 파일에서 삭제
                                            if username in users:
                                                del users[username]
                                                safe_save_json(USERS_PATH, users)
                                            # 해당 사용자의 게시글도 삭제
                                            posts[:] = [post for post in posts if post.get("author") != username]
                                            safe_save_json(POSTS_PATH, posts)
                                            st.success(f"사용자 '{username}'가 삭제되었습니다.")
                                            st.rerun()
                else:
                    st.write("등록된 사용자가 없습니다.")
                
                st.markdown("---")
            
            if st.button("로그아웃"):
                if st.session_state.session_id:
                    secure_auth.logout(st.session_state.session_id)
                st.session_state.session_id = None
                st.session_state.logged_in = False
                st.session_state.current_user = None
                st.session_state.password_changed = False
                st.rerun()
            # 게시물 작성 영역
            st.markdown("### 📝 게시물 작성")
            content = st.text_area("내용", placeholder="무엇을 공유하고 싶으신가요?", max_chars=500, key="post_content")
            submitted = st.button("📝 게시", use_container_width=True, type="primary")
            st.markdown("""
            <hr style="
                border: none;
                height: 3px;
                background: linear-gradient(90deg, #e3f2fd, #bbdefb, #e3f2fd);
                margin: 30px 0;
                border-radius: 2px;
            ">
            """, unsafe_allow_html=True)
            if submitted and content.strip():
                processed_content, url_previews = url_preview_generator.process_text_with_urls(content)
                new_post = {
                    "id": str(uuid.uuid4()),
                    "content": content,
                    "author": st.session_state.current_user,
                    "url_previews": url_previews,
                    "created_at": datetime.now().isoformat(),
                    "comments": [],
                    "public": False
                }
                if USE_SUPABASE:
                    if supabase_save_post(new_post):
                        posts.insert(0, new_post)
                        st.success("게시물이 등록되었습니다!")
                    else:
                        posts.insert(0, new_post)
                        safe_save_json(POSTS_PATH, posts)
                        st.success("게시물이 등록되었습니다! (로컬 모드)")
                else:
                    posts.insert(0, new_post)
                    safe_save_json(POSTS_PATH, posts)
                    st.success("게시물이 등록되었습니다!")
                st.rerun()
            # 게시글 목록 표시 (본인 글과 공개된 글만)
            visible_posts = [post for post in posts if post["author"] == st.session_state.current_user or post.get("public", False)]
            for idx, post in enumerate(visible_posts):
                import re
                import html
                safe_content = html.escape(post["content"])
                url_pattern = r'(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)'
                content_with_links = re.sub(url_pattern, r'<a href="\1" target="_blank" style="color: #1da1f2; text-decoration: none;">\1</a>', safe_content)
                comments_parts = ['<div style="border-top: 1px solid #f0f0f0; margin-top: 16px; padding-top: 16px;">']
                if post.get("comments", []):
                    for c in post.get("comments", []):
                        safe_author = html.escape(c['author'])
                        safe_comment = html.escape(c['content'])
                        comment_html = f'<div style="margin-bottom: 12px; padding: 12px; background: #f8f9fa; border-radius: 8px; border-left: 3px solid #1da1f2;"><div style="font-weight: 600; color: #1da1f2; font-size: 14px; margin-bottom: 4px;">{safe_author} <span style="color: #999; font-weight: normal; font-size: 12px;">• {c['timestamp'][:16]}</span></div><div style="font-size: 14px; line-height: 1.4; color: #333;">{safe_comment}</div></div>'
                        comments_parts.append(comment_html)
                else:
                    comments_parts.append('<div style="color: #999; font-size: 14px; text-align: center; padding: 12px;">아직 댓글이 없습니다. 첫 번째 댓글을 남겨보세요!</div>')
                comments_parts.append('</div>')
                comments_section = ''.join(comments_parts)
                st.markdown(
                    f'<div class="post-card-light" style="border-radius: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.12); padding: 24px; margin-bottom: 24px; width: 100%; box-sizing: border-box;">'
                    f'<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">'
                    f'<span style="font-weight: 600; color: #1da1f2; margin: 0;">{post["author"]}</span>'
                    f'<span style="color: #666; font-size: 13px; margin: 0;">{post["created_at"][:16]}</span>'
                    f'</div>'
                    f'<div class="post-content-light" style="font-size: 17px; margin-bottom: 16px; white-space: pre-wrap; line-height: 1.5;">{content_with_links}</div>'
                    f'{comments_section}'
                    f'</div>',
                    unsafe_allow_html=True
                )
                # URL 미리보기 표시 (카드 밖)
                if post.get("url_previews"):
                    for preview in post["url_previews"]:
                        url_preview_generator.render_url_preview(preview)
                else:
                    urls = url_preview_generator.extract_urls(post["content"])
                    if urls:
                        for url in urls[:2]:
                            try:
                                preview = url_preview_generator.get_url_preview(url)
                                if preview:
                                    url_preview_generator.render_url_preview(preview)
                            except:
                                pass
                # 댓글/공개/삭제 버튼 및 댓글 입력 폼은 기존대로 유지
                
                # 댓글 입력 폼 (댓글 버튼 눌렀을 때만 표시)
                if "comment_open" in st.session_state and st.session_state["comment_open"].get(post['id'], False):
                    st.markdown("**💬 댓글 작성**")
                    with st.form(f"comment_form_{post['id']}", clear_on_submit=True):
                        comment_text = st.text_area("댓글을 입력하세요", key=f"comment_input_{post['id']}", height=80, placeholder="댓글을 남겨보세요...")
                        col_submit, col_cancel = st.columns([1, 1])
                        with col_submit:
                            comment_submit = st.form_submit_button("댓글 등록", use_container_width=True, type="primary")
                        with col_cancel:
                            if st.form_submit_button("취소", use_container_width=True):
                                st.session_state["comment_open"][post['id']] = False
                                st.rerun()
                        
                        if comment_submit and comment_text.strip():
                            post.setdefault("comments", []).append({
                                "author": st.session_state.current_user,
                                "content": comment_text.strip(),
                                "timestamp": datetime.now().isoformat()
                            })
                            if USE_SUPABASE:
                                supabase_update_post(post['id'], {"comments": post["comments"]})
                            else:
                                safe_save_json(POSTS_PATH, posts)
                            
                            # 댓글 입력창 닫기
                            st.session_state["comment_open"][post['id']] = False
                            st.success("댓글이 등록되었습니다!")
                            st.rerun()
except Exception as e:
    st.error(f"예기치 않은 오류가 발생했습니다: {e}") 