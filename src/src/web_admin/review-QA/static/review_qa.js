/**
 * QA审核与修正系统 - 前端逻辑
 */

// API基础URL
const API_BASE = '';

// 全局状态
const state = {
    currentTab: 'unreviewed',
    unreviewedData: [],
    reviewedDocuments: [],
    currentDocument: null,
    reviewedData: [],
    
    // 分页状态
    unreviewedPage: 1,
    reviewedPage: 1,
    pageSize: 20,
    
    // 弹窗状态
    selectedDocument: null,
    pendingApproval: null,
    pendingDeletion: null,
    
    // 统计状态
    currentYear: new Date().getFullYear(),
    currentMonth: new Date().getMonth() + 1,
    monthlyStats: {},
    
    // 编辑追踪状态
    editedSegments: new Map() // 存储被编辑的分段 {segmentId: {question, answer, documentId}}
};

// ==================== 初始化 ====================

document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 QA审核与修正系统初始化...');
    
    // 绑定导航标签切换
    document.querySelectorAll('.nav-tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });
    
    // 绑定分页按钮
    document.getElementById('unreviewed-prev').addEventListener('click', () => changePage('unreviewed', -1));
    document.getElementById('unreviewed-next').addEventListener('click', () => changePage('unreviewed', 1));
    document.getElementById('reviewed-prev').addEventListener('click', () => changePage('reviewed', -1));
    document.getElementById('reviewed-next').addEventListener('click', () => changePage('reviewed', 1));
    
    // 绑定页码跳转
    document.getElementById('unreviewed-jump').addEventListener('click', () => jumpToPage('unreviewed'));
    document.getElementById('reviewed-jump').addEventListener('click', () => jumpToPage('reviewed'));
    document.getElementById('unreviewed-page-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') jumpToPage('unreviewed');
    });
    document.getElementById('reviewed-page-input').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') jumpToPage('reviewed');
    });
    
    // 绑定返回按钮
    document.getElementById('back-to-documents').addEventListener('click', backToDocuments);
    
    // 绑定弹窗按钮
    document.getElementById('confirm-document').addEventListener('click', confirmDocumentSelection);
    document.getElementById('confirm-delete').addEventListener('click', confirmDeletion);
    
    // 绑定统计相关
    document.getElementById('today-stats').addEventListener('click', showMonthlyStatsModal);
    document.getElementById('prev-month').addEventListener('click', () => changeMonth(-1));
    document.getElementById('next-month').addEventListener('click', () => changeMonth(1));
    
    // 绑定logo点击事件
    document.getElementById('logo-icon').addEventListener('click', handleRefreshRequest);
    
    // 绑定刷新确认弹窗
    document.getElementById('cancel-refresh').addEventListener('click', closeRefreshConfirmModal);
    document.getElementById('confirm-refresh').addEventListener('click', confirmRefresh);
    
    // 监听F5和刷新操作 - 使用自定义确认框
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    // 拦截F5键刷新
    document.addEventListener('keydown', (e) => {
        if (e.key === 'F5' || (e.ctrlKey && e.key === 'r')) {
            e.preventDefault();
            handleRefreshRequest(e);
        }
    });
    
    // 加载未审核数据
    loadUnreviewedData();
    
    // 加载已审核文档列表
    loadReviewedDocuments();
    
    // 加载今日统计
    loadTodayStats();
    
    // 加载已审核总数
    loadReviewedTotal();
});

// ==================== 标签切换 ====================

function switchTab(tab) {
    state.currentTab = tab;
    
    // 更新导航标签样式
    document.querySelectorAll('.nav-tab').forEach(t => {
        t.classList.toggle('active', t.dataset.tab === tab);
    });
    
    // 更新内容区域
    document.querySelectorAll('.content-area').forEach(area => {
        area.classList.toggle('active', area.id === `${tab}-area`);
    });
    
    // 如果切换到已审核区域，确保显示文档选择界面
    if (tab === 'reviewed') {
        backToDocuments();
    }
}

function goToHome() {
    console.log('🏠 返回首页并刷新数据');
    
    // 切换到未审核区域
    switchTab('unreviewed');
    
    // 跳转到第一页
    state.unreviewedPage = 1;
    
    // 重新加载数据
    loadUnreviewedData();
    
    // 滚动到顶部
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ==================== 刷新确认功能 ====================

function handleRefreshRequest(e) {
    if (e) e.preventDefault();
    
    // 显示确认弹窗
    showRefreshConfirmModal();
}

function handleBeforeUnload(e) {
    // 如果有未审核数据，阻止默认刷新并显示自定义确认框
    // 注意: beforeunload只能显示浏览器原生对话框，但我们仍然设置以兼容某些场景
    if (state.unreviewedData.length > 0) {
        e.preventDefault();
        e.returnValue = '刷新页面将重新加载未审核列表，由于数据量庞大，加载需要较长时间。';
        return e.returnValue;
    }
}

function showRefreshConfirmModal() {
    document.getElementById('refresh-confirm-modal').classList.add('active');
}

function closeRefreshConfirmModal() {
    document.getElementById('refresh-confirm-modal').classList.remove('active');
}

async function confirmRefresh() {
    closeRefreshConfirmModal();
    // 刷新前保存编辑
    await saveCurrentPageEdits();
    goToHome();
}

// ==================== 未审核区域 ====================

async function loadUnreviewedData() {
    console.log('📥 加载未审核数据...');
    
    showLoading('unreviewed-list');
    
    try {
        const response = await fetch(`${API_BASE}/api/unreviewed/segments`);
        const result = await response.json();
        
        if (result.success) {
            state.unreviewedData = result.data;
            state.unreviewedPage = 1;
            
            console.log(`✅ 加载成功，共 ${result.total} 条数据`);
            
            // 更新计数徽章
            document.getElementById('unreviewed-count').textContent = result.total;
            
            renderUnreviewedList();
        } else {
            showToast('加载失败: ' + result.error, 'error');
            showEmptyState('unreviewed-list', '加载失败');
        }
    } catch (error) {
        console.error('❌ 加载失败:', error);
        showToast('网络错误，请稍后重试', 'error');
        showEmptyState('unreviewed-list', '加载失败');
    }
}

function renderUnreviewedList() {
    const container = document.getElementById('unreviewed-list');
    const pagination = document.getElementById('unreviewed-pagination');
    
    if (state.unreviewedData.length === 0) {
        showEmptyState('unreviewed-list', '暂无待审核的QA');
        pagination.style.display = 'none';
        return;
    }
    
    // 计算分页
    const totalPages = Math.ceil(state.unreviewedData.length / state.pageSize);
    const startIndex = (state.unreviewedPage - 1) * state.pageSize;
    const endIndex = startIndex + state.pageSize;
    const pageData = state.unreviewedData.slice(startIndex, endIndex);
    
    // 渲染列表
    container.innerHTML = pageData.map((item, index) => {
        const globalIndex = startIndex + index + 1;
        return createUnreviewedCard(item, globalIndex);
    }).join('');
    
    // 更新分页信息
    document.getElementById('unreviewed-pagination-info').textContent = 
        `第 ${state.unreviewedPage}/${totalPages} 页，共 ${state.unreviewedData.length} 条`;
    
    // 更新分页按钮状态
    document.getElementById('unreviewed-prev').disabled = state.unreviewedPage === 1;
    document.getElementById('unreviewed-next').disabled = state.unreviewedPage === totalPages;
    
    pagination.style.display = 'flex';
    
    // 绑定事件
    bindUnreviewedEvents();
}

function createUnreviewedCard(item, index) {
    const addMethodBadge = getAddMethodBadge(item.add_method);
    const createdTime = formatTimestamp(item.created_at);
    const classification = item.classification || '-';  // 分类字段，默认'-'
    
    return `
        <div class="qa-card" data-segment-id="${item.id}" data-document-id="${item.document_id}" data-classification="${escapeHtml(classification)}">
            <div class="qa-card-header">
                <div class="qa-card-number">序号: ${index}</div>
                <div class="qa-card-meta">
                    <div class="meta-item">
                        <span class="meta-label">添加时间:</span>
                        <span class="meta-value">${createdTime}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">添加方式:</span>
                        ${addMethodBadge}
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">添加来源:</span>
                        <span class="meta-value">${escapeHtml(item.add_source)}</span>
                    </div>
                    <div class="meta-item classification-item">
                        <span class="meta-label">分类:</span>
                        <span class="classification-badge" data-segment-id="${item.id}" onclick="showClassificationSelector('${item.id}', '${escapeHtml(classification)}')">
                            ${escapeHtml(classification)}
                        </span>
                    </div>
                </div>
            </div>
            <div class="qa-card-content">
                <div class="qa-field">
                    <div class="qa-field-label">问题</div>
                    <textarea class="qa-field-input question-input" rows="3">${escapeHtml(item.question)}</textarea>
                </div>
                <div class="qa-field">
                    <div class="qa-field-label">答案</div>
                    <textarea class="qa-field-input answer-input" rows="5">${escapeHtml(item.answer)}</textarea>
                </div>
            </div>
            <div class="qa-card-actions">
                <button class="btn btn-primary approve-btn">✓ 通过</button>
                <button class="btn btn-danger delete-btn">✗ 删除</button>
            </div>
        </div>
    `;
}

function bindUnreviewedEvents() {
    // 通过按钮
    document.querySelectorAll('.approve-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const card = e.target.closest('.qa-card');
            handleApprove(card);
        });
    });
    
    // 删除按钮
    document.querySelectorAll('.delete-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const card = e.target.closest('.qa-card');
            handleDelete(card, 'unreviewed');
        });
    });
    
    // 文本框自动调整高度和编辑追踪
    document.querySelectorAll('.qa-card').forEach(card => {
        const segmentId = card.dataset.segmentId;
        const documentId = card.dataset.documentId;
        const questionInput = card.querySelector('.question-input');
        const answerInput = card.querySelector('.answer-input');
        
        // 绑定输入事件
        [questionInput, answerInput].forEach(textarea => {
            textarea.addEventListener('input', function() {
                autoResize.call(this);
                // 实时同步到state
                syncEditToState(segmentId, documentId, questionInput.value, answerInput.value);
            });
            autoResize.call(textarea);
        });
    });
}

// 同步编辑内容到state对象
function syncEditToState(segmentId, documentId, question, answer) {
    // 查找原始数据
    const original = state.unreviewedData.find(item => item.id === segmentId);
    if (!original) return;
    
    // 检查是否有变化
    if (original.question !== question || original.answer !== answer) {
        state.editedSegments.set(segmentId, {
            question: question,
            answer: answer,
            documentId: documentId,
            original: {
                question: original.question,
                answer: original.answer
            }
        });
        console.log(`📝 编辑追踪: 分段 ${segmentId} 已修改`);
    } else {
        // 如果恢复原值,从编辑列表中移除
        state.editedSegments.delete(segmentId);
    }
}

function handleApprove(card) {
    const segmentId = card.dataset.segmentId;
    const documentId = card.dataset.documentId;
    const question = card.querySelector('.question-input').value.trim();
    const answer = card.querySelector('.answer-input').value.trim();
    const classification = card.dataset.classification || '-';
    
    if (!question || !answer) {
        showToast('问题和答案不能为空', 'warning');
        return;
    }
    
    // 检查是否已选择分类
    if (!classification || classification === '-') {
        showToast('请先选择文档分类', 'warning');
        return;
    }
    
    // 查找对应的文档ID
    const targetDocId = findDocumentIdByName(classification);
    if (!targetDocId) {
        showToast('无效的文档分类', 'error');
        return;
    }
    
    // 直接审核通过
    performApproval(segmentId, documentId, targetDocId, question, answer, card);
}

function handleDelete(card, area) {
    const segmentId = card.dataset.segmentId;
    const documentId = card.dataset.documentId;
    
    // 保存待删除信息
    state.pendingDeletion = {
        segmentId,
        documentId,
        card,
        area
    };
    
    // 显示确认弹窗
    showConfirmModal();
}

// ==================== 已审核区域 ====================

async function loadReviewedDocuments() {
    console.log('📥 加载已审核文档列表...');
    
    try {
        const response = await fetch(`${API_BASE}/api/reviewed/documents`);
        const result = await response.json();
        
        if (result.success) {
            state.reviewedDocuments = result.data;
            renderDocumentGrid();
        } else {
            showToast('加载文档列表失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('❌ 加载文档列表失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    }
}

function renderDocumentGrid() {
    const container = document.getElementById('document-selection');
    
    const documentIcons = {
        '接线类': '🔌',           // 插头
        '电机类': '⚙️',           // 齿轮
        '触摸屏类': '📱',       // 手机
        '程序类': '💻',           // 笔记本电脑
        '产品型号功能类': '📦', // 包裹
        '产品维修类': '🔧',   // 扫手
        '产品功能类': '⚡',       // 闪电
        'modbus通信地址表_SEN类': '📡', // 卫星
        '产品知识类': '📖',   // 书籍
        '通信参数类': '📊',   // 数据图表
        '下载功能类': '💾',   // 软盘
        '咨询类': '💬',           // 对话框
        '通讯类': '📨',           // 信封
        '操作类': '🎮'            // 游戏手柄
    };
    
    const cards = state.reviewedDocuments.map(doc => `
        <div class="document-card" data-document-id="${doc.id}">
            <div class="document-card-icon">${documentIcons[doc.name] || '📄'}</div>
            <div class="document-card-name">${escapeHtml(doc.name)}<span class="doc-count" id="doc-count-${doc.id}">加载中...</span></div>
        </div>
    `).join('');
    
    container.innerHTML = `
        <div style="grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
            <h2 style="text-align: center; flex: 1; margin: 0;">
                📚 选择文档分类
            </h2>
            <button class="btn btn-primary" id="check-duplicates-btn" style="margin-left: auto;">
                🔍 查重
            </button>
        </div>
        ${cards}
    `;
    
    // 绑定点击事件
    document.querySelectorAll('.document-card').forEach(card => {
        card.addEventListener('click', () => {
            const documentId = card.dataset.documentId;
            loadReviewedData(documentId);
        });
    });
    
    // 重新绑定查重按钮事件
    const checkDuplicatesBtn = document.getElementById('check-duplicates-btn');
    if (checkDuplicatesBtn) {
        checkDuplicatesBtn.addEventListener('click', handleCheckDuplicates);
    }
    
    // 异步加载每个文档的分段条数
    state.reviewedDocuments.forEach(async (doc) => {
        try {
            const response = await fetch(`${API_BASE}/api/reviewed/segments/${doc.id}`);
            const result = await response.json();
            
            if (result.success) {
                const countElement = document.getElementById(`doc-count-${doc.id}`);
                if (countElement) {
                    countElement.textContent = `(${result.total})`;
                }
            }
        } catch (error) {
            console.error(`加载文档 ${doc.name} 条数失败:`, error);
            const countElement = document.getElementById(`doc-count-${doc.id}`);
            if (countElement) {
                countElement.textContent = '';
            }
        }
    });
}

async function loadReviewedData(documentId) {
    console.log(`📥 加载文档数据: ${documentId}`);
    
    const docInfo = state.reviewedDocuments.find(d => d.id === documentId);
    if (!docInfo) return;
    
    state.currentDocument = docInfo;
    
    // 切换到文档详情界面
    document.getElementById('document-selection').style.display = 'none';
    document.getElementById('document-detail').style.display = 'block';
    document.getElementById('document-title').textContent = `📄 ${docInfo.name}`;
    
    showLoading('reviewed-list');
    
    try {
        const response = await fetch(`${API_BASE}/api/reviewed/segments/${documentId}`);
        const result = await response.json();
        
        if (result.success) {
            state.reviewedData = result.data;
            state.reviewedPage = 1;
            
            console.log(`✅ 加载成功，共 ${result.total} 条数据`);
            
            renderReviewedList();
        } else {
            showToast('加载失败: ' + result.error, 'error');
            showEmptyState('reviewed-list', '加载失败');
        }
    } catch (error) {
        console.error('❌ 加载失败:', error);
        showToast('网络错误，请稍后重试', 'error');
        showEmptyState('reviewed-list', '加载失败');
    }
}

function renderReviewedList() {
    const container = document.getElementById('reviewed-list');
    const pagination = document.getElementById('reviewed-pagination');
    
    if (state.reviewedData.length === 0) {
        showEmptyState('reviewed-list', '该文档暂无QA');
        pagination.style.display = 'none';
        return;
    }
    
    // 计算分页
    const totalPages = Math.ceil(state.reviewedData.length / state.pageSize);
    const startIndex = (state.reviewedPage - 1) * state.pageSize;
    const endIndex = startIndex + state.pageSize;
    const pageData = state.reviewedData.slice(startIndex, endIndex);
    
    // 渲染列表
    container.innerHTML = pageData.map((item, index) => {
        const globalIndex = startIndex + index + 1;
        return createReviewedCard(item, globalIndex);
    }).join('');
    
    // 更新分页信息
    document.getElementById('reviewed-pagination-info').textContent = 
        `第 ${state.reviewedPage}/${totalPages} 页，共 ${state.reviewedData.length} 条`;
    
    // 更新分页按钮状态
    document.getElementById('reviewed-prev').disabled = state.reviewedPage === 1;
    document.getElementById('reviewed-next').disabled = state.reviewedPage === totalPages;
    
    pagination.style.display = 'flex';
    
    // 绑定事件
    bindReviewedEvents();
}

function createReviewedCard(item, index) {
    const updatedTime = formatTimestamp(item.updated_at);
    
    return `
        <div class="qa-card" data-segment-id="${item.id}" data-document-id="${item.document_id}">
            <div class="qa-card-header">
                <div class="qa-card-number">序号: ${index}</div>
                <div class="qa-card-meta">
                    <div class="meta-item">
                        <span class="meta-label">最后修改时间:</span>
                        <span class="meta-value">${updatedTime}</span>
                    </div>
                </div>
            </div>
            <div class="qa-card-content">
                <div class="qa-field">
                    <div class="qa-field-label">问题</div>
                    <textarea class="qa-field-input question-input" rows="3">${escapeHtml(item.question)}</textarea>
                </div>
                <div class="qa-field">
                    <div class="qa-field-label">答案</div>
                    <textarea class="qa-field-input answer-input" rows="5">${escapeHtml(item.answer)}</textarea>
                </div>
            </div>
            <div class="qa-card-actions">
                <button class="btn btn-save save-btn">💾 保存</button>
            </div>
        </div>
    `;
}

function bindReviewedEvents() {
    // 保存按钮
    document.querySelectorAll('.save-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const card = e.target.closest('.qa-card');
            handleSave(card);
        });
    });
    
    // 文本框自动调整高度
    document.querySelectorAll('.qa-field-input').forEach(textarea => {
        textarea.addEventListener('input', autoResize);
        autoResize.call(textarea);
    });
}

async function handleSave(card) {
    const segmentId = card.dataset.segmentId;
    const documentId = card.dataset.documentId;
    const question = card.querySelector('.question-input').value.trim();
    const answer = card.querySelector('.answer-input').value.trim();
    const btn = card.querySelector('.save-btn');
    
    if (!question || !answer) {
        showToast('问题和答案不能为空', 'warning');
        return;
    }
    
    btn.disabled = true;
    btn.textContent = '保存中...';
    
    try {
        const response = await fetch(`${API_BASE}/api/segment/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_id: '2df8ca5b-ac31-4dba-8b48-fc09f678b62d',
                document_id: documentId,
                segment_id: segmentId,
                question,
                answer
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('保存成功', 'success');
            // 重新加载数据以更新updated_at
            await loadReviewedData(documentId);
        } else {
            showToast('保存失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('❌ 保存失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '💾 保存';
    }
}

function backToDocuments() {
    document.getElementById('document-selection').style.display = 'grid';
    document.getElementById('document-detail').style.display = 'none';
    state.currentDocument = null;
    state.reviewedData = [];
}

// ==================== 弹窗管理 ====================

function showDocumentModal() {
    const modal = document.getElementById('document-modal');
    const container = document.getElementById('document-options');
    
    container.innerHTML = state.reviewedDocuments.map(doc => `
        <label class="document-option" data-document-id="${doc.id}">
            <input type="radio" name="target-document" value="${doc.id}">
            <span>${escapeHtml(doc.name)}</span>
        </label>
    `).join('');
    
    // 绑定选择事件
    container.querySelectorAll('.document-option').forEach(option => {
        option.addEventListener('click', () => {
            container.querySelectorAll('.document-option').forEach(o => o.classList.remove('selected'));
            option.classList.add('selected');
            option.querySelector('input').checked = true;
            state.selectedDocument = option.dataset.documentId;
        });
    });
    
    modal.classList.add('active');
    state.selectedDocument = null;
}

function closeDocumentModal() {
    document.getElementById('document-modal').classList.remove('active');
    state.selectedDocument = null;
}

// 通用自定义模态框
let customModalCallback = null;

function showCustomModal(title, content, onConfirm) {
    customModalCallback = onConfirm;
    
    // 创建模态框
    let modal = document.getElementById('custom-modal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'custom-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 600px;">
                <div class="modal-header">
                    <h3 id="custom-modal-title"></h3>
                    <button class="modal-close" onclick="closeCustomModal()">&times;</button>
                </div>
                <div class="modal-body" id="custom-modal-body"></div>
                <div class="modal-footer" style="display: flex; gap: 12px; justify-content: flex-end; padding: 16px 24px; border-top: 1px solid var(--border-color);">
                    <button class="btn btn-secondary" onclick="closeCustomModal()">取消</button>
                    <button class="btn btn-primary" onclick="confirmCustomModal()">确认</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        
        // 点击背景关闭
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeCustomModal();
            }
        });
    }
    
    document.getElementById('custom-modal-title').textContent = title;
    document.getElementById('custom-modal-body').innerHTML = content;
    modal.classList.add('active');
}

function closeCustomModal() {
    const modal = document.getElementById('custom-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    customModalCallback = null;
}

async function confirmCustomModal() {
    if (customModalCallback) {
        await customModalCallback();
    }
}

async function confirmDocumentSelection() {
    if (!state.selectedDocument) {
        showToast('请选择目标文档', 'warning');
        return;
    }
    
    const { segmentId, documentId, question, answer, card } = state.pendingApproval;
    const btn = document.getElementById('confirm-document');
    
    btn.disabled = true;
    btn.textContent = '处理中...';
    
    try {
        console.log('📤 发送审核请求:', {
            source_document_id: documentId,
            segment_id: segmentId,
            target_document_id: state.selectedDocument
        });
        
        const response = await fetch(`${API_BASE}/api/segment/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_document_id: documentId,
                segment_id: segmentId,
                target_document_id: state.selectedDocument,
                question,
                answer
            })
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            console.error('❌ HTTP错误:', response.status, errorText);
            throw new Error(`HTTP ${response.status}: ${errorText}`);
        }
        
        const result = await response.json();
        console.log('✅ 审核响应:', result);
        
        if (result.success) {
            showToast(result.message || '审核通过', 'success');
            
            // 从本地数据中移除
            const index = state.unreviewedData.findIndex(item => item.id === segmentId);
            if (index !== -1) {
                state.unreviewedData.splice(index, 1);
            }
            
            // 更新未审核条数
            document.getElementById('unreviewed-count').textContent = state.unreviewedData.length;
            
            // 立即更新已审核条数（+1）
            const reviewedCountElement = document.getElementById('reviewed-count');
            const currentCount = parseInt(reviewedCountElement.textContent) || 0;
            reviewedCountElement.textContent = currentCount + 1;
            
            // 从列表中移除该卡片
            card.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => {
                card.remove();
                // 重新渲染列表（不重新加载数据）
                renderUnreviewedList();
            }, 300);
            
            // 刷新今日统计
            loadTodayStats();
            
            closeDocumentModal();
        } else {
            showToast('操作失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('❌ 操作失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '确定';
    }
}

function showConfirmModal() {
    document.getElementById('confirm-modal').classList.add('active');
}

function closeConfirmModal() {
    document.getElementById('confirm-modal').classList.remove('active');
    state.pendingDeletion = null;
}

async function confirmDeletion() {
    const { segmentId, documentId, card, area } = state.pendingDeletion;
    const btn = document.getElementById('confirm-delete');
    
    btn.disabled = true;
    btn.textContent = '删除中...';
    
    const datasetId = area === 'unreviewed' ? 
        '1397b9d1-8e25-4269-ba12-046059a425b6' : 
        '2df8ca5b-ac31-4dba-8b48-fc09f678b62d';
    
    try {
        const response = await fetch(`${API_BASE}/api/segment/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_id: datasetId,
                document_id: documentId,
                segment_id: segmentId
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('删除成功', 'success');
            
            // 从本地数据中移除
            if (area === 'unreviewed') {
                const index = state.unreviewedData.findIndex(item => item.id === segmentId);
                if (index !== -1) {
                    state.unreviewedData.splice(index, 1);
                }
                document.getElementById('unreviewed-count').textContent = state.unreviewedData.length;
            } else {
                const index = state.reviewedData.findIndex(item => item.id === segmentId);
                if (index !== -1) {
                    state.reviewedData.splice(index, 1);
                }
            }
            
            // 从列表中移除该卡片
            card.style.animation = 'fadeOut 0.3s ease';
            setTimeout(() => {
                card.remove();
                // 重新渲染列表（不重新加载数据）
                if (area === 'unreviewed') {
                    renderUnreviewedList();
                } else {
                    renderReviewedList();
                }
            }, 300);
            
            closeConfirmModal();
        } else {
            showToast('删除失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('❌ 删除失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '确定删除';
    }
}

// ==================== 分页控制 ====================

async function changePage(area, direction) {
    if (area === 'unreviewed') {
        // 分页前自动保存当前页的编辑
        await saveCurrentPageEdits();
        
        const totalPages = Math.ceil(state.unreviewedData.length / state.pageSize);
        const newPage = state.unreviewedPage + direction;
        
        if (newPage >= 1 && newPage <= totalPages) {
            state.unreviewedPage = newPage;
            renderUnreviewedList();
            // 滚动到顶部
            document.getElementById('unreviewed-area').scrollIntoView({ behavior: 'smooth' });
        }
    } else if (area === 'reviewed') {
        // 已审核区域也保存编辑
        await saveReviewedPageEdits();
        
        const totalPages = Math.ceil(state.reviewedData.length / state.pageSize);
        const newPage = state.reviewedPage + direction;
        
        if (newPage >= 1 && newPage <= totalPages) {
            state.reviewedPage = newPage;
            renderReviewedList();
            // 滚动到顶部
            document.getElementById('document-detail').scrollIntoView({ behavior: 'smooth' });
        }
    }
}

function jumpToPage(area) {
    if (area === 'unreviewed') {
        const input = document.getElementById('unreviewed-page-input');
        const targetPage = parseInt(input.value);
        const totalPages = Math.ceil(state.unreviewedData.length / state.pageSize);
        
        if (!targetPage || isNaN(targetPage)) {
            showToast('请输入有效的页码', 'warning');
            return;
        }
        
        if (targetPage < 1 || targetPage > totalPages) {
            showToast(`页码超出范围，请输入1-${totalPages}之间的数字`, 'warning');
            return;
        }
        
        state.unreviewedPage = targetPage;
        renderUnreviewedList();
        input.value = ''; // 清空输入框
        document.getElementById('unreviewed-area').scrollIntoView({ behavior: 'smooth' });
        showToast(`已跳转到第 ${targetPage} 页`, 'success');
        
    } else if (area === 'reviewed') {
        const input = document.getElementById('reviewed-page-input');
        const targetPage = parseInt(input.value);
        const totalPages = Math.ceil(state.reviewedData.length / state.pageSize);
        
        if (!targetPage || isNaN(targetPage)) {
            showToast('请输入有效的页码', 'warning');
            return;
        }
        
        if (targetPage < 1 || targetPage > totalPages) {
            showToast(`页码超出范围，请输入1-${totalPages}之间的数字`, 'warning');
            return;
        }
        
        state.reviewedPage = targetPage;
        renderReviewedList();
        input.value = ''; // 清空输入框
        document.getElementById('document-detail').scrollIntoView({ behavior: 'smooth' });
        showToast(`已跳转到第 ${targetPage} 页`, 'success');
    }
}

// ==================== 工具函数 ====================

function formatTimestamp(timestamp) {
    if (!timestamp) return '-';
    
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function getAddMethodBadge(method) {
    const badges = {
        '旧QA': '<span class="badge badge-old">旧QA</span>',
        '微信每日QA': '<span class="badge badge-wechat">微信每日QA</span>',
        '人工添加': '<span class="badge badge-manual">人工添加</span>',
        '用户添加': '<span class="badge badge-user">用户添加</span>',
        '未知': '<span class="badge badge-unknown">未知</span>'
    };
    
    return badges[method] || badges['未知'];
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDateTime(timestamp) {
    if (!timestamp) return '-';
    try {
        const date = new Date(timestamp * 1000); // 假设timestamp是秒
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}`;
    } catch (e) {
        return '-';
    }
}

function autoResize() {
    // 重置高度以获取正确的scrollHeight
    this.style.height = 'auto';
    
    // 计算需要的高度
    const scrollHeight = this.scrollHeight;
    const minHeight = 60;  // 最小高度
    const maxHeight = 500; // 最大高度
    
    // 设置高度，但不超过最大值
    if (scrollHeight < minHeight) {
        this.style.height = minHeight + 'px';
    } else if (scrollHeight > maxHeight) {
        this.style.height = maxHeight + 'px';
        this.style.overflowY = 'auto';
    } else {
        this.style.height = scrollHeight + 'px';
        this.style.overflowY = 'hidden';
    }
}

// 交互式加载动画状态
const loadingState = {
    clickCount: 0,
    achievements: [
        { threshold: 10, message: '点击大师！' },
        { threshold: 50, message: '点击狂人！' },
        { threshold: 100, message: '点击传说！' },
        { threshold: 200, message: '点击神话！' }
    ],
    tips: [
        '💡 提示：点击 Logo 可以打发时间~',
        '🎮 挑战：看看你能点击多少次！',
        '✨ 加载中，请耐心等待...',
        '🚀 数据即将加载完成！',
        '🎉 继续点击解锁成就！'
    ],
    currentTipIndex: 0
};

function showLoading(containerId) {
    const container = document.getElementById(containerId);
    loadingState.clickCount = 0;
    loadingState.currentTipIndex = 0;
    
    container.innerHTML = `
        <div class="loading">
            <div class="loading-container">
                <div class="interactive-loading">
                    <div class="click-counter" id="click-counter">
                        👆 点击次数: <span id="click-count">0</span>
                    </div>
                    
                    <img src="static/logo.png" 
                         alt="logo" 
                         class="clickable-logo" 
                         id="loading-logo"
                         title="点击我打发时间！">
                    
                    <div class="loading-progress">
                        <div class="loading-progress-bar"></div>
                    </div>
                </div>
                
                <p class="loading-text">正在加载数据...</p>
                <p class="loading-tip" id="loading-tip">${loadingState.tips[0]}</p>
            </div>
        </div>
    `;
    
    // 绑定Logo点击事件
    const logo = document.getElementById('loading-logo');
    if (logo) {
        logo.addEventListener('click', handleLogoClick);
    }
    
    // 循环更换提示
    startTipRotation();
}

function handleLogoClick(e) {
    loadingState.clickCount++;
    
    // 更新计数器
    const countElement = document.getElementById('click-count');
    if (countElement) {
        countElement.textContent = loadingState.clickCount;
        countElement.parentElement.style.animation = 'none';
        setTimeout(() => {
            countElement.parentElement.style.animation = 'pulse 0.3s ease';
        }, 10);
    }
    
    // 创建波纹效果
    createRipple(e);
    
    // 创建点击特效
    createClickEffect(e);
    
    // 检查成就
    checkAchievements();
}

function createRipple(e) {
    const logo = e.currentTarget;
    const ripple = document.createElement('div');
    ripple.className = 'click-ripple';
    
    const rect = logo.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    
    logo.appendChild(ripple);
    
    setTimeout(() => ripple.remove(), 600);
}

function createClickEffect(e) {
    const effects = ['+1', '👍', '✨', '🚀', '🎉', '⭐'];
    const effect = document.createElement('div');
    effect.className = 'click-effect';
    effect.textContent = effects[Math.floor(Math.random() * effects.length)];
    
    effect.style.left = e.clientX + 'px';
    effect.style.top = e.clientY + 'px';
    
    document.body.appendChild(effect);
    
    setTimeout(() => effect.remove(), 1000);
}

function checkAchievements() {
    const achievement = loadingState.achievements.find(
        a => a.threshold === loadingState.clickCount
    );
    
    if (achievement) {
        showAchievement(achievement.message);
    }
}

function showAchievement(message) {
    const popup = document.createElement('div');
    popup.className = 'achievement-popup';
    popup.textContent = message;
    
    document.body.appendChild(popup);
    
    setTimeout(() => popup.remove(), 3000);
}

function startTipRotation() {
    const tipElement = document.getElementById('loading-tip');
    if (!tipElement) return;
    
    setInterval(() => {
        loadingState.currentTipIndex = (loadingState.currentTipIndex + 1) % loadingState.tips.length;
        tipElement.style.animation = 'none';
        setTimeout(() => {
            tipElement.textContent = loadingState.tips[loadingState.currentTipIndex];
            tipElement.style.animation = 'fadeInOut 3s ease-in-out infinite';
        }, 10);
    }, 4000);
}

function showEmptyState(containerId, message) {
    const container = document.getElementById(containerId);
    container.innerHTML = `
        <div class="empty-state">
            <div class="empty-state-icon">📭</div>
            <div class="empty-state-text">${message}</div>
        </div>
    `;
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;
    
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ==================== 统计功能 ====================

async function loadTodayStats() {
    try {
        const response = await fetch(`${API_BASE}/api/stats/today`);
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('today-count').textContent = result.count;
        }
    } catch (error) {
        console.error('❗ 加载今日统计失败:', error);
    }
}

async function loadReviewedTotal() {
    try {
        // 异步加载，不阻塞其他操作
        const response = await fetch(`${API_BASE}/api/stats/total-reviewed`);
        const result = await response.json();
        
        if (result.success) {
            document.getElementById('reviewed-count').textContent = result.total;
        }
    } catch (error) {
        console.error('❗ 加载已审核总数失败:', error);
        // 失败时显示默认值
        document.getElementById('reviewed-count').textContent = '-';
    }
}

async function showMonthlyStatsModal() {
    const modal = document.getElementById('monthly-stats-modal');
    modal.classList.add('active');
    
    // 重置为当前月份
    state.currentYear = new Date().getFullYear();
    state.currentMonth = new Date().getMonth() + 1;
    
    await loadMonthlyStats();
}

function closeMonthlyStatsModal() {
    document.getElementById('monthly-stats-modal').classList.remove('active');
}

async function loadMonthlyStats() {
    try {
        const response = await fetch(
            `${API_BASE}/api/stats/monthly?year=${state.currentYear}&month=${state.currentMonth}`
        );
        const result = await response.json();
        
        if (result.success) {
            state.monthlyStats = result.stats;
            renderCalendar();
        }
    } catch (error) {
        console.error('❗ 加载月度统计失败:', error);
    }
}

function changeMonth(delta) {
    state.currentMonth += delta;
    
    if (state.currentMonth > 12) {
        state.currentMonth = 1;
        state.currentYear++;
    } else if (state.currentMonth < 1) {
        state.currentMonth = 12;
        state.currentYear--;
    }
    
    loadMonthlyStats();
}

function renderCalendar() {
    const container = document.getElementById('calendar-grid');
    const monthText = document.getElementById('current-month');
    
    monthText.textContent = `${state.currentYear}年 ${state.currentMonth}月`;
    
    // 获取月份信息
    const firstDay = new Date(state.currentYear, state.currentMonth - 1, 1);
    const lastDay = new Date(state.currentYear, state.currentMonth, 0);
    const daysInMonth = lastDay.getDate();
    const startWeekday = firstDay.getDay(); // 0 = 周日
    
    const today = new Date();
    const isCurrentMonth = today.getFullYear() === state.currentYear && 
                          today.getMonth() + 1 === state.currentMonth;
    const todayDate = today.getDate();
    
    // 清空并添加星期头
    const weekdays = ['日', '一', '二', '三', '四', '五', '六'];
    let html = weekdays.map(day => 
        `<div class="calendar-header">${day}</div>`
    ).join('');
    
    // 添加空白日期
    for (let i = 0; i < startWeekday; i++) {
        html += '<div class="calendar-day empty"></div>';
    }
    
    // 添加每一天
    for (let day = 1; day <= daysInMonth; day++) {
        const dateStr = `${state.currentYear}-${String(state.currentMonth).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
        const count = state.monthlyStats[dateStr] || 0;
        const isToday = isCurrentMonth && day === todayDate;
        
        let classes = 'calendar-day';
        if (isToday) classes += ' today';
        else if (count > 0) classes += ' has-data';
        
        html += `
            <div class="${classes}">
                <div class="day-number">${day}</div>
                <div class="day-count">${count}条</div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

// 添加fadeOut动画
const style = document.createElement('style');
style.textContent = `
    @keyframes fadeOut {
        from {
            opacity: 1;
            transform: translateY(0);
        }
        to {
            opacity: 0;
            transform: translateY(-20px);
        }
    }
`;
document.head.appendChild(style);

// ==================== 编辑保存功能 ====================

// 保存当前页的编辑(未审核区域)
async function saveCurrentPageEdits() {
    if (state.editedSegments.size === 0) {
        console.log('✅ 没有需要保存的编辑');
        return;
    }
    
    console.log(`💾 开始保存 ${state.editedSegments.size} 个编辑...`);
    
    const savePromises = [];
    
    for (const [segmentId, editData] of state.editedSegments) {
        const promise = fetch(`${API_BASE}/api/segment/update`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_id: '1397b9d1-8e25-4269-ba12-046059a425b6', // 未审核知识库
                document_id: editData.documentId,
                segment_id: segmentId,
                question: editData.question,
                answer: editData.answer
            })
        })
        .then(response => response.json())
        .then(result => {
            if (result.success) {
                console.log(`✅ 分段 ${segmentId} 保存成功`);
                // 更新state中的原始数据
                const item = state.unreviewedData.find(i => i.id === segmentId);
                if (item) {
                    item.question = editData.question;
                    item.answer = editData.answer;
                }
                return { success: true, segmentId };
            } else {
                console.error(`❌ 分段 ${segmentId} 保存失败:`, result.error);
                return { success: false, segmentId, error: result.error };
            }
        })
        .catch(error => {
            console.error(`❌ 分段 ${segmentId} 保存异常:`, error);
            return { success: false, segmentId, error: error.message };
        });
        
        savePromises.push(promise);
    }
    
    const results = await Promise.all(savePromises);
    const successCount = results.filter(r => r.success).length;
    const failCount = results.filter(r => !r.success).length;
    
    // 清空编辑记录
    state.editedSegments.clear();
    
    if (failCount === 0) {
        showToast(`✅ 成功保存 ${successCount} 个编辑`, 'success');
    } else {
        showToast(`⚠️ 保存完成: 成功 ${successCount} 个, 失败 ${failCount} 个`, 'warning');
    }
}

// 保存已审核区域的编辑
async function saveReviewedPageEdits() {
    // 已审核区域的编辑通过保存按钮手动保存，这里不需要自动保存
    console.log('✅ 已审核区域不需要自动保存');
}

// ==================== 查重功能 ====================

// 绑定查重按钮
document.addEventListener('DOMContentLoaded', () => {
    const checkDuplicatesBtn = document.getElementById('check-duplicates-btn');
    if (checkDuplicatesBtn) {
        checkDuplicatesBtn.addEventListener('click', handleCheckDuplicates);
    }
    
    // 相似度滑块
    const similaritySlider = document.getElementById('similarity-slider');
    const similarityValue = document.getElementById('similarity-value');
    if (similaritySlider && similarityValue) {
        similaritySlider.addEventListener('input', (e) => {
            similarityValue.textContent = e.target.value + '%';
        });
    }
    
    // 重新查重按钮
    const recheckBtn = document.getElementById('recheck-btn');
    if (recheckBtn) {
        recheckBtn.addEventListener('click', () => {
            // 显示加载反馈
            const resultsContainer = document.getElementById('duplicate-results');
            resultsContainer.innerHTML = `
                <div class="loading" style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 20px;">
                    <div class="spinner" style="width: 40px; height: 40px; border: 4px solid var(--border-color); border-top-color: var(--primary-color); border-radius: 50%; animation: spin 1s linear infinite;"></div>
                    <p style="margin-top: 16px; font-size: 16px; font-weight: 600; color: var(--primary-color);">正在重新查重...</p>
                </div>
            `;
            
            const threshold = parseInt(document.getElementById('similarity-slider').value) / 100;
            performDuplicateCheck(threshold);
        });
    }
});

async function handleCheckDuplicates() {
    console.log('🔍 开始查重...');
    
    // 显示弹窗
    showDuplicateModal();
    
    // 显示加载动画(使用logo动画)
    const resultsContainer = document.getElementById('duplicate-results');
    resultsContainer.innerHTML = `
        <div class="loading" style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px;">
            <img src="static/logo.png" alt="logo" style="width: 80px; height: 80px; animation: float 3s ease-in-out infinite;">
            <p style="margin-top: 24px; font-size: 18px; font-weight: 600; color: var(--primary-color);">正在查重中...</p>
            <p style="margin-top: 8px; font-size: 14px; color: var(--text-secondary);">请耐心等待...</p>
        </div>
    `;
    
    // 执行查重
    const threshold = parseInt(document.getElementById('similarity-slider').value) / 100;
    await performDuplicateCheck(threshold);
}

async function performDuplicateCheck(threshold) {
    try {
        const response = await fetch(`${API_BASE}/api/reviewed/check-duplicates`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ similarity_threshold: threshold })
        });
        
        const result = await response.json();
        
        if (result.success) {
            renderDuplicateResults(result.data);
        } else {
            showToast('查重失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('❌ 查重失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    }
}

function renderDuplicateResults(data) {
    const resultsContainer = document.getElementById('duplicate-results');
    
    if (data.total_groups === 0) {
        resultsContainer.innerHTML = `
            <div class="duplicate-empty">
                <div class="duplicate-empty-icon">✅</div>
                <div class="duplicate-empty-text">没有发现重复QA！</div>
            </div>
        `;
        return;
    }
    
    let html = `
        <div style="margin-bottom: 20px; padding: 16px; background: var(--bg-color); border-radius: 8px;">
            <strong>查重统计:</strong> 发现 ${data.total_groups} 个重复组，共 ${data.total_duplicates} 条重复条目
        </div>
    `;
    
    data.groups.forEach(group => {
        html += `
            <div class="duplicate-group">
                <div class="duplicate-group-header">
                    <div class="duplicate-group-title">
                        重复组 #${group.group_id} (共${group.count}条) - 平均相似度: ${group.similarity}%
                    </div>
                </div>
                <div class="duplicate-group-items">
                    ${group.items.map((item, index) => `
                        <div class="duplicate-item" data-segment-id="${item.segment_id}">
                            <div class="duplicate-item-header">
                                <div class="duplicate-item-number">${index + 1}</div>
                                <div class="duplicate-item-meta">
                                    <span>📁 ${escapeHtml(item.document_name)}</span>
                                    <span>🏷️ ${escapeHtml(item.classification)}</span>
                                    <span>相似度: ${item.similarity}%</span>
                                    <span>🕒 ${formatDateTime(item.updated_at)}</span>
                                </div>
                                <div class="duplicate-item-actions">
                                    <button class="btn btn-secondary btn-sm" onclick="editDuplicateItem('${item.segment_id}', '${item.document_id}')">
                                        ✏️ 编辑
                                    </button>
                                    <button class="btn btn-danger btn-sm" onclick="confirmDeleteDuplicateItem('${item.segment_id}', '${item.document_id}')">
                                        🗑️ 删除
                                    </button>
                                </div>
                            </div>
                            <div class="duplicate-item-content">
                                <div class="duplicate-item-question">
                                    <strong>问:</strong> ${escapeHtml(item.question)}
                                </div>
                                <div class="duplicate-item-answer">
                                    <strong>答:</strong> ${escapeHtml(item.answer)}
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    });
    
    resultsContainer.innerHTML = html;
}

async function deleteDuplicateItem(segmentId, documentId) {
    if (!confirm('确定要删除这个QA吗？此操作不可恢复！')) {
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/segment/delete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                dataset_id: '2df8ca5b-ac31-4dba-8b48-fc09f678b62d',  // 已审核知识库
                document_id: documentId,
                segment_id: segmentId
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('删除成功', 'success');
            // 重新查重
            const threshold = parseInt(document.getElementById('similarity-slider').value) / 100;
            await performDuplicateCheck(threshold);
        } else {
            showToast('删除失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('❌ 删除失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    }
}

function showDuplicateModal() {
    document.getElementById('duplicate-modal').classList.add('active');
}

function closeDuplicateModal() {
    document.getElementById('duplicate-modal').classList.remove('active');
}

// ==================== 分类选择器 ====================

// 全局变量存储文档分类列表
let documentCategories = [];

// 加载文档分类列表
async function loadDocumentCategories() {
    try {
        const response = await fetch(`${API_BASE}/api/document-categories`);
        const result = await response.json();
        
        if (result.success) {
            documentCategories = result.categories;
            console.log(`✅ 加载文档分类列表: ${documentCategories.length}个`);
        }
    } catch (error) {
        console.error('❌ 加载文档分类列表失败:', error);
    }
}

// 根据分类名称查找文档ID
function findDocumentIdByName(name) {
    const doc = documentCategories.find(cat => cat.name === name);
    return doc ? doc.id : null;
}

// 显示分类选择器
function showClassificationSelector(segmentId, currentClassification) {
    // 创建弹窗
    const modal = document.createElement('div');
    modal.className = 'modal active';
    modal.id = 'classification-selector-modal';
    
    const options = documentCategories.map(cat => `
        <div class="classification-option ${cat.name === currentClassification ? 'selected' : ''}" 
             data-category-name="${escapeHtml(cat.name)}" 
             data-category-id="${cat.id}">
            ${escapeHtml(cat.name)}
        </div>
    `).join('');
    
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>📁 选择文档分类</h3>
                <button class="modal-close" onclick="closeClassificationSelector()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="classification-options">
                    ${options}
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // 绑定选项点击事件
    document.querySelectorAll('.classification-option').forEach(option => {
        option.addEventListener('click', () => {
            const categoryName = option.dataset.categoryName;
            updateSegmentClassification(segmentId, categoryName);
            closeClassificationSelector();
        });
    });
}

// 关闭分类选择器
function closeClassificationSelector() {
    const modal = document.getElementById('classification-selector-modal');
    if (modal) {
        modal.remove();
    }
}

// 更新分段的分类
function updateSegmentClassification(segmentId, categoryName) {
    // 查找对应的卡片
    const card = document.querySelector(`[data-segment-id="${segmentId}"]`);
    if (!card) return;
    
    // 更新data-classification属性
    card.dataset.classification = categoryName;
    
    // 更新显示的分类标签
    const badge = card.querySelector('.classification-badge');
    if (badge) {
        badge.textContent = categoryName;
    }
    
    // 更新state中的数据
    const item = state.unreviewedData.find(i => i.id === segmentId);
    if (item) {
        item.classification = categoryName;
    }
    
    showToast(`分类已更改为: ${categoryName}`, 'success');
}

// 执行审核通过
async function performApproval(segmentId, sourceDocId, targetDocId, question, answer, card) {
    try {
        const response = await fetch(`${API_BASE}/api/segment/approve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                source_document_id: sourceDocId,
                segment_id: segmentId,
                target_document_id: targetDocId,
                question: question,
                answer: answer
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('✅ 审核通过', 'success');
            
            // 从列表中移除
            card.classList.add('fade-out');
            setTimeout(() => {
                state.unreviewedData = state.unreviewedData.filter(item => item.id !== segmentId);
                renderUnreviewedList();
                loadTodayStats();
                loadReviewedTotal();
            }, 300);
        } else {
            showToast('审核失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('❌ 审核失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    }
}

// 初始化时加载分类列表
document.addEventListener('DOMContentLoaded', () => {
    loadDocumentCategories();
    initThemeToggle();
});

// ==================== 主题切换 ====================

function initThemeToggle() {
    // 从 localStorage 读取主题设置
    const savedTheme = localStorage.getItem('review-qa-theme') || 'light';
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
        updateThemeIcon('dark');
    }
    
    // 绑定主题切换按钮
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', toggleTheme);
    }
}

function toggleTheme() {
    const body = document.body;
    const isDark = body.classList.toggle('dark-theme');
    
    // 保存主题设置
    localStorage.setItem('review-qa-theme', isDark ? 'dark' : 'light');
    
    // 更新图标
    updateThemeIcon(isDark ? 'dark' : 'light');
    
    // 显示提示
    showToast(`已切换到${isDark ? '暗色' : '明亮'}主题`, 'success');
}

function updateThemeIcon(theme) {
    const themeIcon = document.querySelector('.theme-icon');
    if (themeIcon) {
        themeIcon.textContent = theme === 'dark' ? '🌙' : '☀️';
    }
}

// ==================== 查重功能增强 ====================

// 编辑重复项
async function editDuplicateItem(segmentId, documentId) {
    try {
        // 获取当前分段数据
        const response = await fetch(`${API_BASE}/api/reviewed/segment/${segmentId}`);
        const result = await response.json();
        
        if (!result.success) {
            showToast('获取分段数据失败', 'error');
            return;
        }
        
        const segment = result.data;
        
        // 解析QA内容
        const content = segment.content || '';
        const lines = content.split('\n');
        let question = '';
        let answer = '';
        
        for (const line of lines) {
            if (line.startsWith('问:')) {
                question = line.substring(2).trim();
            } else if (line.startsWith('答:')) {
                answer = line.substring(2).trim();
            }
        }
        
        // 显示编辑模态框
        const editContent = `
            <div style="padding: 20px;">
                <div style="margin-bottom: 16px;">
                    <label style="display: block; font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">问题：</label>
                    <textarea id="edit-question" rows="3" style="width: 100%; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; font-size: 14px; resize: vertical;">${question}</textarea>
                </div>
                <div style="margin-bottom: 16px;">
                    <label style="display: block; font-weight: 600; margin-bottom: 8px; color: var(--text-primary);">答案：</label>
                    <textarea id="edit-answer" rows="6" style="width: 100%; padding: 12px; border: 1px solid var(--border-color); border-radius: 8px; font-size: 14px; resize: vertical;">${answer}</textarea>
                </div>
            </div>
        `;
        
        showCustomModal('编辑QA', editContent, async () => {
            const newQuestion = document.getElementById('edit-question').value.trim();
            const newAnswer = document.getElementById('edit-answer').value.trim();
            
            if (!newQuestion || !newAnswer) {
                showToast('问题和答案不能为空', 'error');
                return;
            }
            
            await updateDuplicateSegment(segmentId, documentId, newQuestion, newAnswer);
        });
        
    } catch (error) {
        console.error('✖ 编辑失败:', error);
        showToast('编辑失败', 'error');
    }
}

// 更新分段内容
async function updateDuplicateSegment(segmentId, documentId, question, answer) {
    try {
        showToast('正在保存...', 'info');
        
        const response = await fetch(`${API_BASE}/api/reviewed/segments/${segmentId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                document_id: documentId,
                question: question,
                answer: answer
            })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('保存成功，正在重新查重...', 'success');
            
            // 关闭所有模态框
            closeCustomModal();
            closeDuplicateModal();
            
            // 等待一下然后重新查重
            setTimeout(() => {
                handleCheckDuplicates();
            }, 500);
        } else {
            showToast('保存失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('✖ 保存失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    }
}

// 确认删除重复项(使用自定义确认框)
function confirmDeleteDuplicateItem(segmentId, documentId, groupId, groupCount) {
    const content = `
        <div style="padding: 20px; text-align: center;">
            <div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>
            <p style="font-size: 16px; margin-bottom: 12px; color: var(--text-primary);">
                确认要删除这个QA吗？
            </p>
            <p style="font-size: 14px; color: var(--text-secondary);">
                此操作不可恢复！
            </p>
        </div>
    `;
    
    showCustomModal('删除确认', content, () => {
        deleteDuplicateItem(segmentId, documentId);
    });
}

// 删除重复项
async function deleteDuplicateItem(segmentId, documentId) {
    try {
        showToast('正在删除...', 'info');
        
        const response = await fetch(`${API_BASE}/api/reviewed/segments/${segmentId}`, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ document_id: documentId })
        });
        
        const result = await response.json();
        
        if (result.success) {
            showToast('删除成功，正在重新查重...', 'success');
            
            // 关闭确认框
            closeCustomModal();
            
            // 等待一下然后重新查重
            setTimeout(() => {
                handleCheckDuplicates();
            }, 500);
        } else {
            showToast('删除失败: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('✖ 删除失败:', error);
        showToast('网络错误，请稍后重试', 'error');
    }
}
