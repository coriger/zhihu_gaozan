// ==UserScript==
// @name         Zhihu 高赞答案一键导出
// @namespace    http://tampermonkey.net/
// @version      1.2
// @description  自动下拉知乎问题页，抓取高赞答案并导出为Markdown，图片本地化
// @author       Copilot
// @match        https://www.zhihu.com/question/*
// @grant        GM_download
// @grant        GM_addStyle
// @run-at       document-end
// ==/UserScript==

(function() {
    'use strict';
    GM_addStyle(`
      .zhihu-export-btn {
        position: fixed;
        top: 120px;
        right: 40px;
        z-index: 9999;
        background: #4361ee;
        color: #fff;
        border: none;
        border-radius: 6px;
        padding: 12px 18px;
        font-size: 16px;
        cursor: pointer;
        box-shadow: 0 2px 8px rgba(67,97,238,0.15);
      }
    `);
    if (document.querySelector('.zhihu-export-btn')) return;
    const btn = document.createElement('button');
    btn.textContent = '导出高赞答案';
    btn.className = 'zhihu-export-btn';
    btn.onclick = async function() {
        btn.disabled = true;
        let highVoteCount = 0;
        btn.textContent = '下拉加载中... 0/30页';
        // 每次下滑300像素，停顿500ms，最多50次
        let scrollCount = 0;
        while(scrollCount < 30) {
            // 如果已经接近页面底部（剩余不足100像素），先往上滑一段再往下
            if(window.innerHeight + window.scrollY >= document.body.scrollHeight - 100) {
                window.scrollBy(0, -1000); // 向上滑1000像素
                await new Promise(r=>setTimeout(r, 500));
            }
            window.scrollBy(0, 600); // 每次滚动600像素，模拟鼠标滚轮
            await new Promise(r=>setTimeout(r, 200));
            btn.textContent = `下拉加载中... ${scrollCount+1}/30页`;
            scrollCount++;
        }
        btn.textContent = '筛选高赞中...';
        // 筛选高赞答案，收集其链接
        const answers = Array.from(document.querySelectorAll('div.List-item'));
        const answerLinks = [];
        for(const [idx, ans] of answers.entries()){
            // 只查找不在 .ContentItem-meta 下的 meta[itemprop="upvoteCount"] 和 meta[itemprop="url"]
            let upvoteMeta = null, urlMeta = null;
            const metas = ans.querySelectorAll('meta[itemprop]');
            metas.forEach(meta => {
                // 跳过 ContentItem-meta 下的 meta
                if(meta.closest('.ContentItem-meta')) return;
                if(meta.getAttribute('itemprop') === 'upvoteCount') upvoteMeta = meta;
                if(meta.getAttribute('itemprop') === 'url') urlMeta = meta;
            });
            let vote = upvoteMeta ? parseInt(upvoteMeta.content, 10) : 0;
            let answerUrl = urlMeta ? urlMeta.content : '';
            if(vote < 50 || !answerUrl) continue;
            if(!answerUrl.includes('/question/')) continue; // 只保留标准答案链接
            answerLinks.push(answerUrl);
            highVoteCount++;
            btn.textContent = `已发现高赞答案：${highVoteCount} 个`;
        }
        if(answerLinks.length===0){
            btn.disabled = false; btn.textContent = '未找到高赞答案！';
            window.close();
            return;
        }
        console.log(answerLinks)
        btn.textContent = `提交后端生成中... 共${answerLinks.length}个高赞答案`;
        // 发送到后端接口
        fetch('http://127.0.0.1:5000/api/zhihu_batch_answers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({urls: answerLinks})
        })
        .then(r=>r.json())
        .then(res=>{
            window.close(); // 调用接口后自动关闭窗口
        })
        .catch(()=>alert('网络或后端错误！'))
        .finally(()=>{
        });
    };
    document.body.appendChild(btn);

    // 下载图片到本地image目录
    function downloadImage(url, filename){
        GM_download({url, name: filename, saveAs: false});
    }

    // 添加“复制标题和链接”按钮
    if (!document.querySelector('.zhihu-copy-title-url-btn')) {
        const copyBtn = document.createElement('button');
        copyBtn.textContent = '复制标题和链接';
        copyBtn.className = 'zhihu-export-btn zhihu-copy-title-url-btn';
        copyBtn.style.top = '180px';
        copyBtn.onclick = function() {
            // 获取标题
            let title = '';
            // 问题页/回答页
            let h1 = document.querySelector('h1.QuestionHeader-title, h1.QuestionHeader-title, .QuestionHeader-title');
            if (h1) {
                title = h1.textContent.trim();
            } else {
                // 首页、列表页等
                let metaTitle = document.querySelector('title');
                if (metaTitle) {
                    title = metaTitle.textContent.replace(/ - 知乎.*/, '').trim();
                }
            }
            // 获取url
            let url = location.href;
            // 只保留 https://www.zhihu.com/question/xxxxxx 结构
            let match = url.match(/https:\/\/www.zhihu.com\/question\/\d+/);
            if (match) url = match[0];
            // 复制格式：标题\turl
            const text = `${title}\t${url}`;
            navigator.clipboard.writeText(text).then(()=>{
                copyBtn.textContent = '已复制!';
                setTimeout(()=>copyBtn.textContent = '复制标题和链接', 1200);
            });
        };
        document.body.appendChild(copyBtn);
    }

    // 自动导出按钮
    if (!document.querySelector('.zhihu-auto-export-btn')) {
        const autoExportBtn = document.createElement('button');
        autoExportBtn.textContent = '自动导出到本地问题库';
        autoExportBtn.className = 'zhihu-export-btn zhihu-auto-export-btn';
        autoExportBtn.style.top = '240px';
        autoExportBtn.onclick = async function() {
            // 分类列表，初始固定
            const defaultCats = ['爱好', '大萧条', '房价', '感悟', '资产配置'];
            let customCats = [];
            try {
                customCats = JSON.parse(localStorage.getItem('zhihu_custom_cats')||'[]');
            } catch(e) { customCats = []; }
            const allCats = [...defaultCats, ...customCats.filter(c=>!defaultCats.includes(c))];
            // 弹窗选择分类（美观平铺按钮样式）
            let catHtml = `<div id='zhihu-cat-list' style='display:flex;flex-wrap:wrap;gap:10px;justify-content:center;margin-bottom:16px;'>`;
            allCats.forEach(c=>{
                catHtml += `<div class='zhihu-cat-btn' data-cat="${c}" style='padding:8px 18px;border-radius:20px;background:#f3f6fa;color:#333;cursor:pointer;transition:.2s;border:1.5px solid #e0e3e8;font-size:16px;'>${c}</div>`;
            });
            catHtml += `<div class='zhihu-cat-btn' data-cat="__custom__" style='padding:8px 18px;border-radius:20px;background:#f3f6fa;color:#333;cursor:pointer;transition:.2s;border:1.5px solid #e0e3e8;font-size:16px;'>自定义</div>`;
            catHtml += `</div>`;
            catHtml += `<input id='zhihu-cat-input' style='display:none;width:85%;padding:8px 12px;font-size:15px;border-radius:8px;border:1.5px solid #e0e3e8;margin-bottom:10px;' placeholder='输入新分类'/><br>`;
            catHtml += `<button id='zhihu-cat-ok' style='margin-top:8px;padding:10px 32px;background:#4361ee;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer;'>确定导出</button>`;
            // 新增关闭按钮
            catHtml += `<div id='zhihu-cat-close' style='position:absolute;top:12px;right:18px;font-size:22px;color:#888;cursor:pointer;user-select:none;'>×</div>`;
            let div = document.createElement('div');
            div.innerHTML = catHtml;
            div.style = 'position:fixed;top:30%;left:50%;transform:translate(-50%,-50%);background:#fff;padding:32px 40px;z-index:99999;border-radius:14px;box-shadow:0 2px 24px #0002;text-align:center;min-width:340px;';
            div.style.position = 'fixed';
            div.style.boxSizing = 'border-box';
            document.body.appendChild(div);
            // 关闭按钮逻辑
            div.querySelector('#zhihu-cat-close').onclick = ()=>div.remove();
            // 分类选择逻辑
            let selectedCat = '';
            const catBtns = div.querySelectorAll('.zhihu-cat-btn');
            const input = div.querySelector('#zhihu-cat-input');
            catBtns.forEach(btn=>{
                btn.onclick = ()=>{
                    catBtns.forEach(b=>{b.style.background='#f3f6fa';b.style.color='#333';b.style.border='1.5px solid #e0e3e8';});
                    btn.style.background = '#4361ee';
                    btn.style.color = '#fff';
                    btn.style.border = '2px solid #4361ee';
                    selectedCat = btn.dataset.cat;
                    if(selectedCat==='__custom__'){
                        input.style.display='inline-block';
                        setTimeout(()=>input.focus(), 50);
                    }else{
                        input.style.display='none';
                    }
                };
            });
            // 默认选中第一个
            setTimeout(()=>catBtns[0].click(), 10);
            div.querySelector('#zhihu-cat-ok').onclick = async ()=>{
                let cat = selectedCat;
                if(cat==='__custom__') cat = input.value.trim();
                if(!cat) { alert('请选择或填写分类'); return; }
                // 新分类写入localStorage
                if(!defaultCats.includes(cat) && !customCats.includes(cat)) {
                    customCats.push(cat);
                    localStorage.setItem('zhihu_custom_cats', JSON.stringify(customCats));
                }
                // 获取标题
                let title = '';
                let h1 = document.querySelector('h1.QuestionHeader-title, .QuestionHeader-title');
                if (h1) title = h1.textContent.trim();
                else {
                    let metaTitle = document.querySelector('title');
                    if (metaTitle) title = metaTitle.textContent.replace(/ - 知乎.*/, '').trim();
                }
                // 获取url
                let url = location.href;
                let match = url.match(/https:\/\/www.zhihu.com\/question\/\d+/);
                if (match) url = match[0];
                // 调用本地接口
                div.innerHTML = '正在提交...';
                fetch('http://127.0.0.1:5001/add_zhihu_question', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({title, url, category: cat})
                })
                .then(r=>r.json())
                .then(res=>{
                    div.innerHTML = res.success ? '导出成功！' : ('导出失败：'+res.msg);
                    setTimeout(()=>div.remove(), 1200);
                })
                .catch(()=>{
                    div.innerHTML = '网络或本地服务错误！';
                    setTimeout(()=>div.remove(), 1500);
                });
            };
        };
        document.body.appendChild(autoExportBtn);
    }
})();
