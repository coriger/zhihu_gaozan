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
})();
