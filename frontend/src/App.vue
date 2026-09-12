<template>
  <router-view v-if="isAuthCallbackRoute" />
  <div v-else-if="!authReady" class="auth-loading-screen">
    <div class="auth-loading-card">
      <div class="auth-loading-mark"></div>
      <strong>正在校验登录状态</strong>
      <span>请稍候...</span>
    </div>
  </div>
  <AuthLogin v-else-if="!authUser" @authenticated="handleAuthenticated" />
  <el-container v-else class="app-shell">
    <el-header class="app-topnav">
      <button class="topnav-brand" type="button" @click="router.push('/smart-ask')">
        <img src="/datapivot-logo.svg" alt="DataPulse" class="topnav-logo" />
        <span class="topnav-brand-name">DataPulse</span>
        <span class="topnav-brand-env">脉策智能</span>
      </button>

      <el-menu
        :default-active="activeMenu"
        class="topnav-menu"
        mode="horizontal"
        :ellipsis="true"
        @select="handleMenuSelect"
      >
        <el-menu-item
          v-for="item in primaryMenuItems"
          :key="item.path"
          :index="item.path"
        >
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>
        <el-sub-menu
          v-if="managementMenuItems.length"
          index="management"
        >
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>管理配置</span>
          </template>
          <el-menu-item
            v-for="item in managementMenuItems"
            :key="item.path"
            :index="item.path"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <template #title>{{ item.label }}</template>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>

      <div class="topnav-actions">
        <button
          class="topnav-history"
          type="button"
          title="任务记录"
          @click="historyDrawerVisible = true"
        >
          <span class="topnav-history-icon" aria-hidden="true"></span>
          <span class="topnav-history-label">任务</span>
          <span v-if="historySessions.length" class="topnav-history-count">{{ historySessions.length }}</span>
        </button>

        <button class="topnav-command" type="button" @click="openCommandPalette">
          <span class="topnav-command-icon" aria-hidden="true"></span>
          <span class="topnav-command-text">搜索模块、跳转功能</span>
          <span class="topnav-command-kbd">⌘K</span>
        </button>

        <div class="topnav-user">
          <button class="topnav-user-chip" type="button" @click.stop="toggleUserMenu">
            <span class="topnav-user-avatar">{{ authUserInitial }}</span>
            <span class="topnav-user-status" :class="{ 'is-online': backendOk }" aria-hidden="true"></span>
            <span class="topnav-user-meta">
              <span class="topnav-user-name">{{ authUserName }}</span>
              <span class="topnav-user-role">{{ authRoleLabel }}</span>
            </span>
            <span class="topnav-user-arrow" aria-hidden="true"></span>
          </button>
          <transition name="user-menu-rise">
            <div v-if="userMenuVisible" class="topnav-user-dropdown" @click.stop>
              <button
                v-if="authRole === 'super_admin' && appFeatureAccess.admin_console"
                type="button"
                @click="openAdminConsole"
              >
                <strong>系统控制台</strong>
                <span>功能开关与灰度发布</span>
              </button>
              <button v-if="appFeatureAccess.app_password_change" type="button" @click="openPasswordDialog">
                <strong>修改密码</strong>
                <span>更新当前账号登录密码</span>
              </button>
              <button class="danger" type="button" @click="handleLogout">
                <strong>退出登录</strong>
                <span>清除本机登录状态</span>
              </button>
            </div>
          </transition>
        </div>
      </div>
    </el-header>

    <el-container class="app-body">
      <el-header v-if="!isDataPulseRoute" class="context-bar">
        <div class="context-left">
          <span class="context-title">{{ currentTitle }}</span>
          <span v-if="currentSubtitle" class="context-subtitle">{{ currentSubtitle }}</span>
          <button v-if="showBackToConsole" class="context-back" type="button" @click="backToConsole">
            返回控制台
          </button>
        </div>
        <div class="context-right">
          <span class="backend-status-chip" :class="{ 'is-online': backendOk, 'is-offline': !backendOk }">
            <span class="backend-status-dot"></span>
            {{ backendOk ? '后端在线' : '后端异常' }}
          </span>
          <div class="clock">{{ currentTime }}</div>
        </div>
      </el-header>

      <el-main class="page-wrap" :class="{ 'page-wrap-smart': isDataPulseRoute }">
        <router-view v-slot="{ Component }">
          <keep-alive :include="cachedPageNames">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </el-container>

    <el-drawer
      v-model="historyDrawerVisible"
      title="全部任务"
      size="420px"
      custom-class="history-drawer"
    >
      <div class="history-drawer-head">
        <div>
          <div class="history-drawer-title">{{ historySessions.length }} 个任务</div>
          <div class="history-drawer-desc">选择任意任务可恢复到分析工作台。</div>
        </div>
        <button
          v-if="historySessions.length && appFeatureAccess.app_history_clear"
          class="history-drawer-clear"
          type="button"
          :disabled="isClearingHistory"
          @click="clearHistoryList"
        >
          {{ isClearingHistory ? '清空中...' : '清空全部' }}
        </button>
      </div>
      <div v-if="historySessions.length || currentRunningTask" class="history-drawer-list">
        <!-- 抽屉里的虚拟"当前执行任务"行 -->
        <article
          v-if="currentRunningTask"
          class="history-item history-drawer-item history-item-running"
          :key="currentRunningTask.id"
          :aria-label="'当前任务：' + currentRunningTask.title"
          @click="handleRunningTaskClick; historyDrawerVisible = false"
        >
          <div class="history-drawer-index">{{ currentRunningTask.status === 'pending_confirmation' ? '待确认' : '执行' }}</div>
          <div class="history-item-main">
            <div class="history-item-top">
              <div class="history-item-title">{{ currentRunningTask.title }}</div>
              <div class="history-item-status">
                <TaskStatusIndicator
                  :variant="currentRunningTask.status"
                  :show-text-label="true"
                />
              </div>
            </div>
            <div class="history-drawer-meta-row">
              <span class="history-drawer-dataset">{{ currentRunningTask.datasetName }}</span>
              <span class="history-drawer-time">刚刚发起</span>
            </div>
          </div>
        </article>

        <article
          v-for="(item, index) in historySessions"
          :key="item.id"
          class="history-item history-drawer-item"
          :class="{ 'history-item-active': item.id === activeHistoryId }"
          @click="openHistorySession(item); historyDrawerVisible = false"
        >
          <div class="history-drawer-index">{{ String(index + 1).padStart(2, '0') }}</div>
          <div class="history-item-main">
            <div class="history-item-top">
              <div class="history-item-title">{{ item.title }}</div>
              <div class="history-item-status">
                <TaskStatusIndicator
                  :variant="inferTaskVariant(item)"
                  :show-text-label="true"
                />
                <span v-if="item.id === activeHistoryId" class="history-item-badge">当前</span>
              </div>
            </div>
            <div class="history-drawer-meta-row">
              <span class="history-drawer-dataset">{{ item.datasetName || '自动路由数据集' }}</span>
              <span class="history-drawer-time">{{ item.updatedAt }}</span>
            </div>
          </div>
          <button
            v-if="appFeatureAccess.app_history_delete"
            class="history-item-delete"
            type="button"
            aria-label="删除任务"
            @click.stop="removeHistoryItem(item.id)"
          >
            <span class="history-item-delete-icon" aria-hidden="true"></span>
          </button>
        </article>
      </div>
      <div v-else class="history-empty history-drawer-empty">
        <div class="history-empty-title">暂无任务</div>
        <div class="history-empty-desc">发起分析后，这里会显示你的任务记录。</div>
      </div>
    </el-drawer>

    <el-dialog
      v-model="passwordDialogVisible"
      title="修改密码"
      width="420px"
      custom-class="password-dialog"
      :close-on-click-modal="false"
    >
      <div class="password-panel">
        <span class="password-panel-icon">锁</span>
        <div>
          <h3>更新登录密码</h3>
          <p>建议使用至少 8 位，并包含数字和字母的密码。</p>
        </div>
      </div>
      <div class="password-form">
        <label>
          <span>原密码</span>
          <div class="dialog-password-control">
            <input
              v-model="passwordForm.old_password"
              :type="passwordVisible.old ? 'text' : 'password'"
              autocomplete="current-password"
              placeholder="请输入当前密码"
              @keydown.enter="submitPasswordChange"
            />
            <button
              class="dialog-password-eye"
              type="button"
              :aria-label="passwordVisible.old ? '隐藏原密码' : '显示原密码'"
              @click="passwordVisible.old = !passwordVisible.old"
            >
              <el-icon><component :is="passwordVisible.old ? Hide : View" /></el-icon>
            </button>
          </div>
        </label>
        <label>
          <span>新密码</span>
          <div class="dialog-password-control">
            <input
              v-model="passwordForm.new_password"
              :type="passwordVisible.next ? 'text' : 'password'"
              autocomplete="new-password"
              placeholder="至少 8 位"
              @keydown.enter="submitPasswordChange"
            />
            <button
              class="dialog-password-eye"
              type="button"
              :aria-label="passwordVisible.next ? '隐藏新密码' : '显示新密码'"
              @click="passwordVisible.next = !passwordVisible.next"
            >
              <el-icon><component :is="passwordVisible.next ? Hide : View" /></el-icon>
            </button>
          </div>
        </label>
        <label>
          <span>确认新密码</span>
          <div class="dialog-password-control">
            <input
              v-model="passwordForm.confirm_password"
              :type="passwordVisible.confirm ? 'text' : 'password'"
              autocomplete="new-password"
              @keydown.enter="submitPasswordChange"
            />
            <button
              class="dialog-password-eye"
              type="button"
              :aria-label="passwordVisible.confirm ? '隐藏确认密码' : '显示确认密码'"
              @click="passwordVisible.confirm = !passwordVisible.confirm"
            >
              <el-icon><component :is="passwordVisible.confirm ? Hide : View" /></el-icon>
            </button>
          </div>
        </label>
      </div>
      <template #footer>
        <button class="dialog-ghost-button" type="button" @click="passwordDialogVisible = false">取消</button>
        <button class="dialog-primary-button" type="button" :disabled="passwordSaving" @click="submitPasswordChange">
          {{ passwordSaving ? '保存中...' : '确认修改' }}
        </button>
      </template>
    </el-dialog>

    <div
      v-if="showAdminConsoleFloat"
      class="admin-console-float"
      :style="adminConsoleFloatStyle"
      @pointerdown="startAdminConsoleFloatDrag"
    >
      <button
        class="admin-console-float-main"
        :class="{ dragging: adminConsoleFloatDragging }"
        type="button"
        @click.stop="handleAdminConsoleFloatOpen"
      >
        <el-icon><Setting /></el-icon>
        <span>控制台</span>
      </button>
      <button
        class="admin-console-float-close"
        type="button"
        aria-label="关闭控制台悬浮入口"
        @pointerdown.stop
        @click.stop="dismissAdminConsoleFloat"
      >
        x
      </button>
    </div>
    <SqlDebugFloat />
  </el-container>

  <!-- 全局命令面板（⌘K / Ctrl+K） -->
  <transition name="palette-fade">
    <div v-if="commandPaletteVisible" class="command-palette-mask" @click.self="closeCommandPalette">
      <div class="command-palette" role="dialog" aria-label="命令面板">
        <div class="command-palette-search">
          <span class="command-palette-search-icon" aria-hidden="true"></span>
          <input
            ref="commandInputRef"
            v-model="commandQuery"
            class="command-palette-input"
            type="text"
            placeholder="输入模块名称或关键词…"
            autocomplete="off"
            @keydown.esc="closeCommandPalette"
            @keydown.enter.prevent="runActiveCommand"
            @keydown.up.prevent="moveCommandCursor(-1)"
            @keydown.down.prevent="moveCommandCursor(1)"
          />
          <span class="command-palette-hint">ESC 关闭</span>
        </div>
        <div class="command-palette-list">
          <button
            v-for="(cmd, idx) in filteredCommands"
            :key="cmd.path"
            class="command-palette-item"
            :class="{ 'is-active': idx === commandCursor }"
            type="button"
            @mouseenter="commandCursor = idx"
            @click="runCommand(cmd)"
          >
            <el-icon class="command-palette-item-icon"><component :is="cmd.icon" /></el-icon>
            <span class="command-palette-item-body">
              <span class="command-palette-item-label">{{ cmd.label }}</span>
              <span class="command-palette-item-path">{{ cmd.path }}</span>
            </span>
          </button>
          <div v-if="!filteredCommands.length" class="command-palette-empty">没有匹配的模块</div>
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { ChatLineRound, Coin, Collection, Connection, Cpu, Document, Hide, Lock, MagicStick, Monitor, Operation, Setting, Share, UploadFilled, View } from '@element-plus/icons-vue'
import AuthLogin from './auth/AuthLogin.vue'
import SqlDebugFloat from './components/SqlDebugFloat.vue'
import TaskStatusIndicator from './components/TaskStatusIndicator.vue'
import { preloadRouteComponents } from './router'
import { changePassword, clearAuthToken, getCurrentUser, healthCheck, logout } from './api/index.js'
import { useDataPulseSession } from './state/smartAskSession.js'
import { useDataPulseHistory } from './state/smartAskHistory.js'
import { useDataPulseTaskView } from './state/smartAskTaskView.js'
import { useFeatureFlags } from './state/featureFlags.js'

const route = useRoute()
const router = useRouter()
const session = useDataPulseSession()
const {
  historySessions,
  activeHistoryId,
  buildHistoryScope,
  setHistoryScope,
  loadHistory,
  syncHistory,
  removeHistory,
  clearHistory,
  requestRestore,
  setActiveHistory,
} = useDataPulseHistory()
const {
  runningSessionId,
  runningTaskStatus,
  completedTaskId,
  viewingTaskId,
  isViewingReadonly,
  setRunningSessionId,
  setViewingTask,
  switchViewToDefault,
  clearRunningSessionId,
  switchViewToRunning,
} = useDataPulseTaskView()
const {
  features: featureFlags,
  ready: featureFlagsReady,
  loadFeatureFlags,
  clearFeatureFlags,
} = useFeatureFlags()
const appFeatureKeys = [
  'app_history_clear',
  'app_history_delete',
  'admin_console',
  'app_password_change',
]
const appFeatureAccess = computed(() => appFeatureKeys.reduce((map, key) => {
  map[key] = isFeatureEnabled(key)
  return map
}, {}))
const backendOk = ref(false)
const authUser = ref(null)
const authReady = ref(false)
const passwordDialogVisible = ref(false)
const passwordSaving = ref(false)
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: ''
})
const passwordVisible = ref({
  old: false,
  next: false,
  confirm: false,
})
const currentTime = ref('')
const historyDrawerVisible = ref(false)
const isClearingHistory = ref(false)
const userMenuVisible = ref(false)

/* ── 全局命令面板（⌘K / Ctrl+K）── */
const commandPaletteVisible = ref(false)
const commandQuery = ref('')
const commandCursor = ref(0)
const commandInputRef = ref(null)

const roleRank = {
  super_admin: 4,
  admin: 3,
  business_admin: 2,
  user: 1
}

const menuItems = [
  { path: '/smart-ask', label: '智能分析工作台', icon: ChatLineRound, minRole: 'user', featureKey: 'smart_ask_workspace' },
  { path: '/sql-debug', label: 'SQL调试台', icon: Monitor, minRole: 'user', featureKey: 'dataset_sql_preview_run' },
  { path: '/agents', label: '智能体编排配置', icon: Cpu, minRole: 'admin', featureKey: 'agent_management' },
  { path: '/datasets', label: '数据资产管理', icon: Collection, minRole: 'admin', featureKey: 'dataset_management' },
  { path: '/databases', label: '数据连接管理', icon: Coin, minRole: 'admin', featureKey: 'database_management' },
  { path: '/ai-models', label: '模型服务配置', icon: MagicStick, minRole: 'admin', featureKey: 'ai_model_config' },
  { path: '/report-config', label: '报告模板配置', icon: Document, minRole: 'admin', featureKey: 'report_config' },
  { path: '/advanced-capabilities', label: '进阶能力中心', icon: Operation, minRole: 'admin', featureKey: 'advanced_capabilities' },
  { path: '/feishu-sync', label: '飞书数据同步', icon: Connection, minRole: 'admin', featureKey: 'feishu_sync' },
  { path: '/runtime-migration', label: '迁移发布管理', icon: UploadFilled, minRole: 'super_admin', featureKey: 'runtime_migration' },
  { path: '/organization-trees', label: '组织树管理', icon: Share, minRole: 'super_admin', featureKey: 'organization_tree_management' },
  { path: '/employee-permissions', label: '角色权限管理', icon: Lock, minRole: 'super_admin', featureKey: 'employee_permissions' },
  { path: '/admin-console', label: '系统控制台', icon: Setting, minRole: 'super_admin', featureKey: 'admin_console', hidden: true }
]

const routeComponentNamesByPath = {
  '/smart-ask': 'DataPulse',
  '/sql-debug': 'SqlDebug',
  '/agents': 'AgentManagement',
  '/datasets': 'DatasetManagement',
  '/bookshelves': 'Bookshelves',
  '/databases': 'Databases',
  '/ai-models': 'AIModels',
  '/report-config': 'DatasetReportConfig',
  '/advanced-capabilities': 'AdvancedCapabilities',
  '/feishu-sync': 'FeishuSync',
  '/runtime-migration': 'RuntimeMigration',
  '/organization-trees': 'OrganizationTrees',
  '/employee-permissions': 'EmployeePermissions',
  '/admin-console': 'AdminConsole',
}

const subtitleMap = {
  '/smart-ask': '',
  '/sql-debug': '快速生成、执行与核对问数 SQL',
  '/agents': '维护核心智能体提示词与执行规则',
  '/datasets': '治理数据集元数据、书架与Golden SQL',
  '/databases': '管理 PostgreSQL 与其他业务数据连接',
  '/ai-models': '配置默认模型、通道与调用参数',
  '/report-config': '维护数据集对应的报告模板与展示规范',
  '/advanced-capabilities': '管理进阶问数 Skill、MCP 和 SQL Server 工具链路',
  '/feishu-sync': '管理飞书多维表格同步、日志与任务控制',
  '/runtime-migration': '导出导入运行态配置，发布前自动备份可回滚',
  '/organization-trees': '维护多套独立组织树类型与树形节点',
  '/employee-permissions': '维护员工身份映射、角色与可访问范围'
}

const activeMenu = computed(() => route.path)
const isAuthCallbackRoute = computed(() => route.path === '/auth/callback')
const isDataPulseRoute = computed(() => route.path === '/smart-ask')
const showBackToConsole = computed(() => route.query?.from === 'admin-console' && route.path !== '/admin-console')
const authRole = computed(() => authUser.value?.role || 'user')
const authRoleLabel = computed(() => ({ super_admin: '超级管理员', admin: '管理员', business_admin: '业务管理员', user: '普通用户' }[authRole.value] || '普通用户'))
const canAccessRole = (minRole) => (roleRank[authRole.value] || 0) >= (roleRank[minRole] || 0)
const isFeatureEnabled = (key) => {
  if (!key) return true
  const feature = featureFlags.value?.[key]
  if (!featureFlagsReady.value || !feature) return true
  if (typeof feature.available === 'boolean') return feature.available
  return Boolean(feature.enabled)
}
const hasLoadedFeatureDecision = (key) => Boolean(key && featureFlagsReady.value && featureFlags.value?.[key])
const canAccessMenuItem = (item) => {
  if (!item) return true
  if (hasLoadedFeatureDecision(item.featureKey)) {
    return isFeatureEnabled(item.featureKey)
  }
  return canAccessRole(item.minRole)
}
const availableMenuItems = computed(() => menuItems.filter((item) => !item.hidden && canAccessMenuItem(item)))
const primaryMenuItems = computed(() => availableMenuItems.value.filter((item) => item.path === '/smart-ask' || item.path === '/sql-debug'))
const managementMenuItems = computed(() => availableMenuItems.value.filter((item) => item.path !== '/smart-ask' && item.path !== '/sql-debug'))

/* 命令面板：按关键词过滤当前账号可访问的模块 */
const filteredCommands = computed(() => {
  const q = commandQuery.value.trim().toLowerCase()
  const list = availableMenuItems.value || []
  if (!q) return list
  return list.filter((item) => (
    String(item.label || '').toLowerCase().includes(q)
    || String(item.path || '').toLowerCase().includes(q)
  ))
})

const cachedPageNames = computed(() => (
  Array.from(new Set(availableMenuItems.value.map((item) => routeComponentNamesByPath[item.path]).filter(Boolean)))
))
const currentTitle = computed(() => menuItems.find((item) => item.path === route.path)?.label || '智能分析工作台')
const currentSubtitle = computed(() => subtitleMap[route.path] || '经营分析工作台')
const activeDatasetIds = computed(() => session.activeDatasetIds.value || [])
// 虚拟"当前执行/待确认任务"：session 在跑或待确认时显示在历史列表顶部，不持久化
const currentRunningTask = computed(() => {
  const status = session.state?.status
  if (status !== 'running' && status !== 'waiting_confirmation') return null
  const question = String(session.state?.question || '').trim()
  if (!question) return null
  return {
    id: '__current_running__',
    title: question.slice(0, 24),
    datasetName: status === 'waiting_confirmation' ? '待确认' : '正在分析中',
    status: status === 'waiting_confirmation' ? 'pending_confirmation' : 'running',
    isVirtual: true,
  }
})
const cleanDisplayName = (value) => {
  const text = String(value || '').trim()
  if (!text || /^[?\s]+$/.test(text)) return ''
  return text.replace(/^\?+\s*/, '')
}
const authUserName = computed(() => (
  cleanDisplayName(authUser.value?.name)
  || cleanDisplayName(authUser.value?.permission_name)
  || cleanDisplayName(authUser.value?.username)
  || cleanDisplayName(authUser.value?.zh_name)
  || cleanDisplayName(authUser.value?.union_id)
  || '已登录'
))
const authUserInitial = computed(() => String(authUserName.value || '登').slice(0, 1).toUpperCase())

const refreshClock = () => {
  currentTime.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

const pingBackend = async () => {
  try {
    await healthCheck()
    backendOk.value = true
  } catch {
    backendOk.value = false
  }
}

const refreshAuthUser = async () => {
  try {
    const data = await getCurrentUser()
    authUser.value = data?.authenticated ? (data.user || {}) : null
    syncHistoryScope()
    if (authUser.value) {
      loadFeatureFlags(true)
        .then(() => enforceRouteAccess())
        .catch(() => {})
      syncHistory().catch(() => {})
      scheduleRoutePreload()
    } else clearFeatureFlags()
  } catch {
    authUser.value = null
    clearFeatureFlags()
    syncHistoryScope()
  } finally {
    authReady.value = true
  }
}

const syncHistoryScope = () => {
  if (!authUser.value) {
    setHistoryScope('anonymous')
    return
  }
  setHistoryScope(buildHistoryScope(authUser.value))
}

const handleAuthenticated = async (user) => {
  authUser.value = user || null
  syncHistoryScope()
  if (authUser.value) {
    loadFeatureFlags(true)
      .then(() => enforceRouteAccess())
      .catch(() => {})
    syncHistory().catch(() => {})
    scheduleRoutePreload()
  } else clearFeatureFlags()
  authReady.value = true
  enforceRouteAccess()
}

const submitPasswordChange = async () => {
  if (passwordSaving.value) return
  if (authRole.value === 'super_admin') {
    ElMessage.warning('超级管理员密码由 .env 管理，请修改 DATAPULSE_ADMIN_PASSWORD')
    return
  }
  if (!passwordForm.value.old_password || !passwordForm.value.new_password) {
    ElMessage.warning('请填写原密码和新密码')
    return
  }
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }
  if (passwordForm.value.new_password.length < 8) {
    ElMessage.warning('新密码至少需要 8 位')
    return
  }
  passwordSaving.value = true
  try {
    await changePassword({
      old_password: passwordForm.value.old_password,
      new_password: passwordForm.value.new_password
    })
    passwordDialogVisible.value = false
    passwordForm.value = { old_password: '', new_password: '', confirm_password: '' }
    passwordVisible.value = { old: false, next: false, confirm: false }
    ElMessage({
      message: '密码已修改，请重新登录',
      type: 'success',
      duration: 2200,
      customClass: 'app-toast-modern',
    })
    clearAuthToken()
    authUser.value = null
    clearFeatureFlags()
    syncHistoryScope()
  } finally {
    passwordSaving.value = false
  }
}

const toggleUserMenu = () => {
  userMenuVisible.value = !userMenuVisible.value
}

const closeUserMenu = () => {
  userMenuVisible.value = false
}

/* ── 命令面板行为 ── */
const openCommandPalette = () => {
  commandPaletteVisible.value = true
  commandQuery.value = ''
  commandCursor.value = 0
  userMenuVisible.value = false
  nextTick(() => {
    commandInputRef.value?.focus()
  })
}

const closeCommandPalette = () => {
  commandPaletteVisible.value = false
  commandQuery.value = ''
  commandCursor.value = 0
}

const moveCommandCursor = (delta) => {
  const total = filteredCommands.value.length
  if (!total) return
  commandCursor.value = (commandCursor.value + delta + total) % total
}

const runCommand = (cmd) => {
  if (!cmd) return
  closeCommandPalette()
  if (route.path !== cmd.path) router.push(cmd.path)
}

const runActiveCommand = () => {
  runCommand(filteredCommands.value[commandCursor.value])
}

const handleCommandHotkey = (event) => {
  if ((event.metaKey || event.ctrlKey) && String(event.key).toLowerCase() === 'k') {
    event.preventDefault()
    if (commandPaletteVisible.value) closeCommandPalette()
    else openCommandPalette()
  }
}

const openPasswordDialog = () => {
  closeUserMenu()
  passwordDialogVisible.value = true
}

const ADMIN_CONSOLE_LAST_ROUTE_KEY = 'datapulse_admin_console_last_route'

const getAdminConsoleTarget = () => {
  const fallback = '/admin-console'
  const saved = localStorage.getItem(ADMIN_CONSOLE_LAST_ROUTE_KEY) || sessionStorage.getItem(ADMIN_CONSOLE_LAST_ROUTE_KEY) || ''
  return saved.startsWith('/admin-console') ? saved : fallback
}

const openAdminConsole = () => {
  closeUserMenu()
  router.push(getAdminConsoleTarget())
}

const backToConsole = () => {
  router.push(getAdminConsoleTarget())
}

const ADMIN_CONSOLE_FLOAT_POSITION_KEY = 'datapulse_admin_console_float_position'
const ADMIN_CONSOLE_FLOAT_HIDDEN_KEY = 'datapulse_admin_console_float_hidden'
const ADMIN_CONSOLE_FLOAT_TOGGLE_EVENT = 'datapulse-admin-console-float-toggle'
const adminConsoleFloatVisible = ref(false)
const adminConsoleFloatDragging = ref(false)
const adminConsoleFloatPosition = ref({ x: 0, y: 0 })
let adminConsoleFloatMoved = false
let adminConsoleFloatOffset = { x: 0, y: 0 }

const getDefaultAdminConsoleFloatPosition = () => ({
  x: Math.max(16, window.innerWidth - 164),
  y: Math.max(88, window.innerHeight - 118),
})

const clampAdminConsoleFloatPosition = (position) => {
  const width = 154
  const height = 56
  return {
    x: Math.min(Math.max(12, Number(position?.x) || 0), Math.max(12, window.innerWidth - width)),
    y: Math.min(Math.max(76, Number(position?.y) || 0), Math.max(76, window.innerHeight - height)),
  }
}

const persistAdminConsoleFloatState = () => {
  sessionStorage.setItem(ADMIN_CONSOLE_FLOAT_POSITION_KEY, JSON.stringify(adminConsoleFloatPosition.value))
  sessionStorage.setItem(ADMIN_CONSOLE_FLOAT_HIDDEN_KEY, adminConsoleFloatVisible.value ? '0' : '1')
}

const restoreAdminConsoleFloatState = () => {
  const hidden = sessionStorage.getItem(ADMIN_CONSOLE_FLOAT_HIDDEN_KEY) !== '0'
  adminConsoleFloatVisible.value = !hidden
  try {
    const saved = JSON.parse(sessionStorage.getItem(ADMIN_CONSOLE_FLOAT_POSITION_KEY) || 'null')
    adminConsoleFloatPosition.value = clampAdminConsoleFloatPosition(saved || getDefaultAdminConsoleFloatPosition())
  } catch {
    adminConsoleFloatPosition.value = getDefaultAdminConsoleFloatPosition()
  }
}

const adminConsoleFloatStyle = computed(() => ({
  left: `${adminConsoleFloatPosition.value.x}px`,
  top: `${adminConsoleFloatPosition.value.y}px`,
}))

const showAdminConsoleFloat = computed(() => (
  authRole.value === 'super_admin'
  && appFeatureAccess.value.admin_console
  && adminConsoleFloatVisible.value
))

const stopAdminConsoleFloatDrag = () => {
  if (!adminConsoleFloatDragging.value) return
  adminConsoleFloatDragging.value = false
  persistAdminConsoleFloatState()
  window.removeEventListener('pointermove', handleAdminConsoleFloatDrag)
  window.removeEventListener('pointerup', stopAdminConsoleFloatDrag)
}

const handleAdminConsoleFloatDrag = (event) => {
  if (!adminConsoleFloatDragging.value) return
  adminConsoleFloatPosition.value = clampAdminConsoleFloatPosition({
    x: event.clientX - adminConsoleFloatOffset.x,
    y: event.clientY - adminConsoleFloatOffset.y,
  })
  adminConsoleFloatMoved = true
}

const startAdminConsoleFloatDrag = (event) => {
  if (event.button !== 0) return
  adminConsoleFloatDragging.value = true
  adminConsoleFloatMoved = false
  adminConsoleFloatOffset = {
    x: event.clientX - adminConsoleFloatPosition.value.x,
    y: event.clientY - adminConsoleFloatPosition.value.y,
  }
  window.addEventListener('pointermove', handleAdminConsoleFloatDrag)
  window.addEventListener('pointerup', stopAdminConsoleFloatDrag)
}

const handleAdminConsoleFloatOpen = () => {
  if (adminConsoleFloatMoved) {
    adminConsoleFloatMoved = false
    return
  }
  openAdminConsole()
}

const dismissAdminConsoleFloat = () => {
  adminConsoleFloatVisible.value = false
  persistAdminConsoleFloatState()
}

const handleAdminConsoleFloatResize = () => {
  adminConsoleFloatPosition.value = clampAdminConsoleFloatPosition(adminConsoleFloatPosition.value)
  persistAdminConsoleFloatState()
}

const handleAdminConsoleFloatToggle = (event) => {
  const visible = Boolean(event?.detail?.visible)
  adminConsoleFloatVisible.value = visible
  if (visible && (!adminConsoleFloatPosition.value.x || !adminConsoleFloatPosition.value.y)) {
    adminConsoleFloatPosition.value = getDefaultAdminConsoleFloatPosition()
  }
  persistAdminConsoleFloatState()
}

const handleLogout = async () => {
  try {
    await logout()
    clearAuthToken()
    authUser.value = null
    clearFeatureFlags()
    syncHistoryScope()
    ElMessage({
      message: '已退出登录',
      type: 'success',
      duration: 1800,
      customClass: 'app-toast-modern',
    })
  } catch {
    clearAuthToken()
    authUser.value = null
    clearFeatureFlags()
    syncHistoryScope()
  }
  if (route.path !== '/smart-ask') {
    router.replace('/smart-ask')
  }
}

const refreshCurrentPage = () => {
  window.location.reload()
}

const handleMenuSelect = (index) => {
  if (!index || index === route.path) return
  const target = menuItems.find((item) => item.path === index)
  if (target && !canAccessMenuItem(target)) {
    ElMessage.warning('该功能暂未开放')
    return
  }
  router.push(index)
}

const fallbackRoute = () => availableMenuItems.value[0]?.path || '/smart-ask'

const enforceRouteAccess = () => {
  if (!authUser.value || isAuthCallbackRoute.value) return
  const target = menuItems.find((item) => item.path === route.path)
  if (target && !canAccessMenuItem(target)) {
    const nextPath = fallbackRoute()
    if (route.path !== nextPath) router.replace(nextPath)
  }
}

// 新版外壳：任务历史以右侧抽屉呈现。切换/新建任务后自动收起抽屉。
const pulseHistoryPanel = () => {
  historyDrawerVisible.value = false
}

const openHistorySession = async (item) => {
  if (!item?.id) return
  setActiveHistory(item.id)
  // 如果点击的就是当前运行中/待确认/刚完成的任务，直接切回对应视图
  if (runningSessionId.value === item.id || completedTaskId.value === item.id) {
    switchViewToRunning()
    await router.push('/smart-ask')
    pulseHistoryPanel()
  } else if (runningSessionId.value) {
    // 只要有后台运行中/待确认任务，都以只读模式打开历史，不打断当前任务
    setViewingTask(item.id)
    await requestRestore(item.id, { readonly: true })
    await router.push('/smart-ask')
    pulseHistoryPanel()
  } else {
    // 没有活动任务时才恢复历史并重置当前会话
    switchViewToDefault()
    requestRestore(item.id)
    await router.push('/smart-ask')
    pulseHistoryPanel()
  }
}

const removeHistoryItem = (id) => {
  removeHistory(id)
}

// 根据 history item 推断 TaskStatusIndicator 的 variant（仅历史项）
// 注意：执行中状态由 currentRunningTask 虚拟行单独处理
const inferTaskVariant = (item) => {
  if (item?.status === 'running' || (runningSessionId.value === item?.id && runningTaskStatus.value === 'running')) return 'running'
  const result = item?.reportSnapshot?.result || {}
  if (result.requires_confirmation) return 'pending_confirmation'
  if (result.error) return 'failed'
  return 'completed'
}

const createFreshChat = async () => {
  setActiveHistory('')
  switchViewToDefault()
  await router.push('/smart-ask')
  window.dispatchEvent(new CustomEvent('datapulse-create-fresh-chat'))
  pulseHistoryPanel()
}

// 点击左侧执行中虚拟任务行：直接切回实时执行视图
const handleRunningTaskClick = async () => {
  switchViewToRunning()
  setActiveHistory(runningSessionId.value || '')
  await router.push('/smart-ask')
  pulseHistoryPanel()
}

const clearHistoryList = async () => {
  try {
    await ElMessageBox.confirm(
      '清空后将删除当前保存的全部任务记录。',
      '清空任务',
      {
        type: 'info',
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
        customClass: 'sa-message-box',
      }
    )
  } catch {
    // user cancelled
    return
  }

  isClearingHistory.value = true
  try {
    await clearHistory()
    ElMessage.success('任务已清空')
  } catch (error) {
    ElMessage.error('清空失败，任务记录已恢复，请稍后重试')
  } finally {
    isClearingHistory.value = false
  }
}

let clockTimer = null
let healthTimer = null
let historyFocusTimer = null
let routePreloadScheduled = false

const scheduleRoutePreload = () => {
  if (routePreloadScheduled) return
  routePreloadScheduled = true
  const preload = () => {
    preloadRouteComponents(cachedPageNames.value).catch(() => {})
  }
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(preload, { timeout: 2000 })
  } else {
    window.setTimeout(preload, 800)
  }
}

// 工作台头部「任务」入口 → 打开右侧任务抽屉
const handleHistoryFocus = () => {
  if (route.path !== '/smart-ask') {
    router.push('/smart-ask')
  }
  if (historyFocusTimer) {
    clearTimeout(historyFocusTimer)
  }
  historyFocusTimer = window.setTimeout(() => {
    historyDrawerVisible.value = true
  }, 60)
}

const handleGlobalClick = () => {
  closeUserMenu()
}

const handleFeatureFlagsUpdated = async () => {
  if (authUser.value) {
    await loadFeatureFlags(true)
  } else {
    clearFeatureFlags()
  }
  enforceRouteAccess()
}

const handleUnauthorized = () => {
  // 登录态失效（接口 401）：清空当前用户 → 模板回落到登录页
  if (authUser.value) {
    authUser.value = null
    clearFeatureFlags()
    syncHistoryScope()
  }
}

onMounted(() => {
  refreshClock()
  pingBackend()
  refreshAuthUser()
  clockTimer = setInterval(refreshClock, 1000)
  healthTimer = setInterval(pingBackend, 10000)
  window.addEventListener('datapulse-history-focus', handleHistoryFocus)
  window.addEventListener('click', handleGlobalClick)
  window.addEventListener('datapulse-feature-flags-updated', handleFeatureFlagsUpdated)
  window.addEventListener('datapulse:unauthorized', handleUnauthorized)
  window.addEventListener('keydown', handleCommandHotkey)
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(healthTimer)
  if (historyFocusTimer) {
    clearTimeout(historyFocusTimer)
  }
  window.removeEventListener('datapulse-history-focus', handleHistoryFocus)
  window.removeEventListener('click', handleGlobalClick)
  window.removeEventListener('datapulse-feature-flags-updated', handleFeatureFlagsUpdated)
  window.removeEventListener('datapulse:unauthorized', handleUnauthorized)
  window.removeEventListener('keydown', handleCommandHotkey)
})

watch(() => route.path, (path) => {
  enforceRouteAccess()
  if (path === '/smart-ask') {
    loadHistory()
    syncHistory()
  }
})

watch(authUser, () => {
  syncHistoryScope()
  if (authUser.value) syncHistory()
  enforceRouteAccess()
})
onMounted(() => {
  restoreAdminConsoleFloatState()
  window.addEventListener('resize', handleAdminConsoleFloatResize)
  window.addEventListener(ADMIN_CONSOLE_FLOAT_TOGGLE_EVENT, handleAdminConsoleFloatToggle)
})

onUnmounted(() => {
  stopAdminConsoleFloatDrag()
  window.removeEventListener('resize', handleAdminConsoleFloatResize)
  window.removeEventListener(ADMIN_CONSOLE_FLOAT_TOGGLE_EVENT, handleAdminConsoleFloatToggle)
})
</script>

<style>
:root {
  --shell-bg: var(--bg-page, #F4F7FA);
  --panel-bg: var(--bg-card, #FFFFFF);
  --panel-border: var(--border, #E5E7EB);
  --ink-strong: var(--text-title, #111827);
  --ink-soft: var(--text-muted, #9CA3AF);
  --brand: #6366F1;
  --brand-soft: #EEF2FF;
}

* {
  box-sizing: border-box;
}

html,
body,
#app {
  margin: 0;
  height: 100%;
  background: var(--bg-page);
  font-family: var(--font-sans, 'Microsoft YaHei UI', 'Microsoft YaHei', 'PingFang SC', sans-serif);
  color: var(--text-title, #111827);
}

.app-shell {
  height: 100%;
}

.auth-loading-screen {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: var(--bg-page, #EDF2F6);
}

.auth-loading-card {
  width: 260px;
  padding: 26px;
  border-radius: var(--radius-lg, 16px);
  display: grid;
  justify-items: center;
  gap: 9px;
  background: var(--bg-card, #FFFFFF);
  border: 1px solid var(--border, #E5E7EB);
  box-shadow: var(--shadow-lg, 0 4px 8px rgba(0,0,0,0.03), 0 16px 40px rgba(0,0,0,0.07));
  color: var(--text-title, #111827);
}

.auth-loading-card span {
  color: var(--text-secondary, #6B7280);
  font-size: 12px;
}

.auth-loading-mark {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: rgba(23, 20, 60, 0.88);
  animation: auth-loading-pulse 1.2s ease-in-out infinite alternate;
}

@keyframes auth-loading-pulse {
  from { transform: scale(0.92); opacity: 0.72; }
  to { transform: scale(1); opacity: 1; }
}

/* ==========================================================================
   外壳：顶部横向导航（新版布局 · 无左侧栏）
   ========================================================================== */

.app-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* ── 顶栏容器 ── */
.app-topnav {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 0 0 auto;
  height: 60px !important;
  padding: 0 20px;
  background: #ffffff;
  border-bottom: 1px solid var(--border, #E6EAF2) !important;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  z-index: 40;
}

/* ── 品牌区 ── */
.topnav-brand {
  display: inline-flex;
  align-items: center;
  gap: 9px;
  flex: 0 0 auto;
  padding: 5px 10px 5px 6px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  transition: background var(--duration-fast, 150ms) var(--ease-out, ease);
}

.topnav-brand:hover {
  background: var(--brand-primary-soft, #EEF2FF);
}

.topnav-logo {
  height: 26px;
  width: auto;
  object-fit: contain;
  flex-shrink: 0;
}

.topnav-brand-name {
  font-size: 17px;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-title, #111827);
  white-space: nowrap;
}

.topnav-brand-env {
  padding: 2px 7px;
  border-radius: 999px;
  background: var(--brand-gradient, linear-gradient(135deg, #6366F1 0%, #3B82F6 100%));
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

/* ── 横向主导航 ── */
.topnav-menu.el-menu {
  flex: 1 1 auto;
  min-width: 0;
  height: 60px;
  border-bottom: 0 !important;
  background: transparent;
}

.topnav-menu.el-menu--horizontal > .el-menu-item,
.topnav-menu.el-menu--horizontal > .el-sub-menu > .el-sub-menu__title {
  position: relative;
  display: inline-flex;
  align-items: center;
  height: 60px !important;
  line-height: 60px !important;
  padding: 0 13px !important;
  margin: 0 1px;
  border-bottom: 0 !important;
  background: transparent !important;
  color: var(--text-secondary, #475569) !important;
  font-size: 14px;
  font-weight: 600;
}

.topnav-menu .el-menu-item .el-icon,
.topnav-menu .el-sub-menu__title .el-icon {
  width: 18px;
  height: 18px;
  margin-right: 6px;
  font-size: 17px;
}

.topnav-menu.el-menu--horizontal > .el-menu-item:hover,
.topnav-menu.el-menu--horizontal > .el-sub-menu > .el-sub-menu__title:hover {
  color: var(--brand-primary, #6366F1) !important;
  background: var(--brand-primary-soft, #EEF2FF) !important;
}

.topnav-menu.el-menu--horizontal > .el-menu-item.is-active,
.topnav-menu.el-menu--horizontal > .el-sub-menu.is-active > .el-sub-menu__title {
  color: var(--brand-primary, #6366F1) !important;
  background: var(--brand-primary-soft, #EEF2FF) !important;
  border-bottom: 0 !important;
}

.topnav-menu.el-menu--horizontal > .el-menu-item.is-active::after,
.topnav-menu.el-menu--horizontal > .el-sub-menu.is-active > .el-sub-menu__title::after {
  content: '';
  position: absolute;
  left: 12px;
  right: 12px;
  bottom: 10px;
  height: 2px;
  border-radius: 2px;
  background: var(--brand-primary, #6366F1);
}

/* 管理配置下拉（弹层渲染到 body，需全局选择器） */
.el-menu--popup {
  min-width: 190px;
  padding: 6px !important;
  border-radius: 12px !important;
  border: 1px solid var(--border, #E5E7EB);
  box-shadow: 0 16px 40px rgba(30, 27, 75, 0.16) !important;
}

.el-menu--popup .el-menu-item {
  height: 36px;
  line-height: 36px;
  margin: 2px 0;
  padding: 0 12px !important;
  border-radius: 9px;
  font-size: 13px;
  color: var(--text-secondary, #475569) !important;
  background: transparent !important;
}

.el-menu--popup .el-menu-item:hover,
.el-menu--popup .el-menu-item.is-active {
  background: var(--brand-primary-soft, #EEF2FF) !important;
  color: var(--brand-primary, #6366F1) !important;
}

.el-menu--popup .el-menu-item.is-active {
  font-weight: 700;
}

/* ── 顶栏右侧动作区 ── */
.topnav-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.topnav-history {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 34px;
  padding: 0 12px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: 999px;
  background: #ffffff;
  color: var(--text-secondary, #475569);
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
  transition: all var(--duration-fast, 150ms) var(--ease-out, ease);
}

.topnav-history:hover {
  border-color: var(--brand-primary, #6366F1);
  background: var(--brand-primary-soft, #EEF2FF);
  color: var(--brand-primary, #6366F1);
}

.topnav-history-icon {
  flex: 0 0 auto;
  position: relative;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 1.7px solid currentColor;
}

.topnav-history-icon::after {
  content: '';
  position: absolute;
  left: 50%;
  top: 50%;
  width: 1.7px;
  height: 4px;
  border-radius: 2px;
  background: currentColor;
  transform: translate(-50%, -100%);
  transform-origin: bottom center;
}

.topnav-history-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 17px;
  height: 17px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--brand-primary, #6366F1);
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
}

.topnav-command {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 34px;
  width: 236px;
  padding: 0 10px 0 12px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: 999px;
  background: var(--bg-soft, #F6F8FC);
  color: var(--text-muted, #94A3B8);
  font-size: 13px;
  cursor: pointer;
  transition: all var(--duration-fast, 150ms) var(--ease-out, ease);
}

.topnav-command:hover {
  border-color: var(--brand-primary, #6366F1);
  background: #ffffff;
  color: var(--text-secondary, #475569);
}

.topnav-command-icon {
  flex: 0 0 auto;
  position: relative;
  width: 13px;
  height: 13px;
  border-radius: 50%;
  border: 1.7px solid currentColor;
}

.topnav-command-icon::after {
  content: '';
  position: absolute;
  left: 10px;
  top: 10px;
  width: 6px;
  height: 1.7px;
  border-radius: 2px;
  background: currentColor;
  transform: rotate(45deg);
  transform-origin: left center;
}

.topnav-command-text {
  flex: 1 1 auto;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: left;
}

.topnav-command-kbd {
  flex: 0 0 auto;
  padding: 1px 6px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: 6px;
  background: #ffffff;
  font-family: var(--font-mono, monospace);
  font-size: 10.5px;
  letter-spacing: 0.04em;
  color: var(--text-muted, #94A3B8);
}
.history-item {
  position: relative;
  display: flex;
  align-items: flex-start;
  /* bug 2026-08-25 全角色方案：卡片死硬固定 100px（!important 防内部样式覆盖），
     4 个大小永远一致；内容溢出被 overflow hidden 截断 */
  flex: none !important;
  height: 100px !important;
  min-height: 100px !important;
  max-height: 100px !important;
  box-sizing: border-box;
  gap: 10px;
  width: 100%;
  padding: 12px 14px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  animation: history-item-enter 0.24s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.history-item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 12px;
  bottom: 12px;
  width: 3px;
  border-radius: 999px;
  background: transparent;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.history-item:hover {
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.07);
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  transform: translateY(-1px);
}

.history-item-active {
  border-color: rgba(99, 102, 241, 0.25);
  background: rgba(99, 102, 241, 0.1);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.08);
}

.history-item-active::before {
  background: var(--brand-primary, #6366F1);
}

.history-item-active .history-item-title {
  color: #ffffff;
  font-weight: 600;
}

.history-item-main {
  min-width: 0;
  flex: 1;
  /* 卡片内容垂直居中：标题在上，底行(时间+状态)在下 */
  display: flex;
  flex-direction: column;
  justify-content: center;
  height: 100%;
  gap: 6px;
}

/* 卡片底行：时间靠左，状态靠右 */
.history-item-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  min-width: 0;
}

.history-item-top {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding-right: 2px;
  min-width: 0;
  flex: 1;
}

.history-item-title {
  font-size: 12px;
  line-height: 1.52;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.85);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-width: 0;
  /* 标题只占自然高度，不拉伸，由 main 垂直居中 */
  flex: 0 0 auto;
  /* 避免两行标题贴到右侧删除按钮 */
  padding-right: 4px;
}

.history-item-badge {
  flex-shrink: 0;
  height: 17px;
  padding: 0 6px;
  border-radius: 999px;
  background: var(--brand-primary, #6366F1);
  color: #ffffff;
  font-size: 10px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
}

/* 状态指示容器：标题 + 状态指示器 + 当前 badge 同行排列 */
.history-item-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: auto;
}

/* 虚拟"当前执行任务"行：与历史项区分，左红竖条 + 微红底 */
.history-item-running {
  position: relative;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(99, 102, 241, 0.06) 100%);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 12px;
  margin-bottom: 10px;
  padding-right: 14px;
}

.history-item-running::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 3px;
  border-radius: 2px;
  background: var(--brand-primary, #6366F1);
  opacity: 0.9;
}

.history-item-running .history-item-title {
  font-weight: 600;
}

.history-item-meta,
.history-item-time {
  margin-top: 6px;
  font-size: 11px;
  line-height: 1.4;
  color: rgba(255, 255, 255, 0.55);
}

.history-item-delete {
  width: 22px;
  height: 22px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  font-size: 13px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 1px;
  transition: all 0.18s ease;
}

.history-item-delete-icon {
  position: relative;
  width: 10px;
  height: 10px;
  display: inline-flex;
}

.history-item-delete-icon::before,
.history-item-delete-icon::after {
  content: '';
  position: absolute;
  left: 4px;
  top: 0;
  width: 1.5px;
  height: 10px;
  border-radius: 999px;
  background: currentColor;
}

.history-item-delete-icon::before {
  transform: rotate(45deg);
}

.history-item-delete-icon::after {
  transform: rotate(-45deg);
}

.history-item-delete:hover {
  border-color: var(--border, #E5E7EB);
  background: var(--bg-card, #FFFFFF);
  color: var(--text-secondary, #6B7280);
  box-shadow: var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04));
}

@keyframes history-item-enter {
  from {
    opacity: 0;
    transform: translateX(-5px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.history-empty {
  min-height: 176px;
  border: 1px dashed var(--border-hover, #D1D5DB);
  border-radius: var(--radius-md, 12px);
  background: var(--bg-soft, #F3F4F6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 18px;
}

.history-empty-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-title, #111827);
}

.history-empty-desc {
  margin-top: 6px;
  font-size: 10px;
  line-height: 1.6;
  color: var(--text-secondary, #6B7280);
}

.history-drawer {
  border-radius: 20px 0 0 20px;
  overflow: hidden;
  border-left: 1px solid rgba(17, 24, 39, 0.08);
  box-shadow: 0 24px 56px rgba(15, 23, 42, 0.12);
}

.history-drawer .el-drawer__header {
  margin-bottom: 0;
  padding: 24px 26px 16px;
  border-bottom: 1px solid var(--border, #E5E7EB);
  background: var(--bg-card, #FFFFFF);
}

.history-drawer .el-drawer__title {
  color: var(--text-title, #111827);
  font-size: 20px;
  font-weight: 900;
  letter-spacing: -0.02em;
}

.history-drawer .el-drawer__body {
  padding: 18px 18px 22px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #F8F8F7;
}

.history-drawer-head {
  position: relative;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding: 16px;
  border: 1px solid rgba(17, 24, 39, 0.08);
  border-radius: 16px;
  background: #FFFFFF;
  box-shadow: 0 10px 22px rgba(15, 23, 42, 0.045);
}

.history-drawer-title {
  color: var(--text-title, #111827);
  font-size: 16px;
  font-weight: 900;
}

.history-drawer-desc {
  margin-top: 4px;
  color: var(--text-secondary, #6B7280);
  font-size: 12px;
}

.history-drawer-clear {
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--error-soft, #EEF2FF);
  border-radius: 999px;
  background: var(--error-soft, #EEF2FF);
  color: var(--error, #6366F1);
  font-size: 11px;
  font-weight: 800;
  cursor: pointer;
}

.history-drawer-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-right: 4px;
}

.history-drawer-item {
  position: relative;
  margin: 0;
  align-items: center;
  /* 抽屉内卡片保持自然高度，不参与侧栏卡片的均分拉伸 */
  flex: 0 0 auto;
  gap: 14px;
  min-height: 94px;
  padding: 18px 46px 18px 18px;
  border-radius: 16px;
  border-color: rgba(17, 24, 39, 0.07);
  background: #FFFFFF;
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.035);
}

.history-drawer-item:hover {
  border-color: rgba(17, 24, 39, 0.12);
  box-shadow: 0 12px 26px rgba(15, 23, 42, 0.055);
  background: #FFFFFF;
}

.history-drawer-item.history-item-active {
  border-color: rgba(99, 102, 241, 0.18);
  background: #F5F6F8;
  box-shadow:
    0 10px 24px rgba(15, 23, 42, 0.045),
    inset 4px 0 0 #6366F1;
}

.history-drawer-item.history-item-active::before {
  background: transparent;
}

.history-drawer-index {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #6B7280;
  font-size: 13px;
  font-weight: 900;
  background: #F1F0EE;
  border: 1px solid rgba(17, 24, 39, 0.08);
}

.history-drawer-item .history-item-title {
  color: #111827;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.45;
  text-shadow: none;
  -webkit-line-clamp: 2;
}

.history-drawer-item.history-item-active .history-item-title {
  color: #111827;
  font-weight: 900;
}

.history-drawer-meta-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

/* 抽屉内 main 恢复默认块布局，不继承侧栏卡片的垂直居中 */
.history-drawer-item .history-item-main {
  display: block;
  height: auto;
  justify-content: normal;
  gap: 0;
}

.history-drawer-dataset {
  max-width: 210px;
  height: 24px;
  padding: 0 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  color: #6B7280;
  font-size: 12px;
  font-weight: 800;
  background: #F1F0EE;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-drawer-time {
  color: #9CA3AF;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.history-drawer-item .history-item-delete {
  position: absolute;
  right: 12px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0;
}

.history-drawer-item:hover .history-item-delete {
  opacity: 1;
}

.history-drawer-empty {
  flex: 1;
}

.sa-message-box {
  border-radius: var(--radius-xl, 20px) !important;
  border: 1px solid var(--border, #E5E7EB) !important;
  box-shadow: var(--shadow-lg, 0 4px 8px rgba(0,0,0,0.03), 0 16px 40px rgba(0,0,0,0.07)) !important;
  padding: 18px 18px 16px !important;
}

.sa-message-box .el-message-box__header {
  padding-bottom: 6px;
}

.sa-message-box .el-message-box__title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-title, #111827);
}

.sa-message-box .el-message-box__headerbtn {
  top: 16px;
  right: 16px;
}

.sa-message-box .el-message-box__status {
  width: 22px;
  height: 22px;
  margin-right: 10px;
  border-radius: 999px;
  background: var(--bg-soft, #F3F4F6);
  color: var(--text-secondary, #6B7280) !important;
}

.sa-message-box .el-message-box__content {
  padding-top: 4px;
  padding-bottom: 8px;
}

.sa-message-box .el-message-box__message {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-body, #374151);
}

.sa-message-box .el-message-box__btns {
  padding-top: 8px;
}

.sa-message-box .el-button {
  min-width: 96px;
  height: 36px;
  border-radius: 999px;
}

/* ===== 顶栏右上：用户菜单 ===== */
.topnav-user {
  position: relative;
}

.topnav-user-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 38px;
  padding: 0 10px 0 5px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: 999px;
  background: #ffffff;
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-fast, 150ms) var(--ease-out, ease);
}

.topnav-user-chip:hover {
  border-color: var(--brand-primary, #6366F1);
  background: var(--brand-primary-soft, #EEF2FF);
}

.topnav-user-avatar {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12.5px;
  font-weight: 700;
  color: #ffffff;
  background: var(--brand-gradient, linear-gradient(135deg, #6366F1 0%, #3B82F6 100%));
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.35);
}

.topnav-user-status {
  flex: 0 0 auto;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CBD5E1;
}

.topnav-user-status.is-online {
  background: #10B981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.16);
}

.topnav-user-meta {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 1px;
  min-width: 0;
}

.topnav-user-name {
  max-width: 108px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12.5px;
  font-weight: 700;
  color: var(--text-title, #111827);
}

.topnav-user-role {
  font-size: 10.5px;
  color: var(--text-muted, #94A3B8);
}

.topnav-user-arrow {
  flex: 0 0 auto;
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-top: 5px solid var(--text-muted, #94A3B8);
}

.topnav-user-dropdown {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  z-index: 60;
  width: 224px;
  padding: 6px;
  border-radius: var(--radius-md, 14px);
  background: #ffffff;
  border: 1px solid var(--border, #DFE3F0);
  box-shadow: 0 16px 40px rgba(30, 27, 75, 0.22);
}

.topnav-user-dropdown button {
  display: flex;
  flex-direction: column;
  gap: 2px;
  width: 100%;
  padding: 9px 10px;
  border: 0;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background var(--duration-fast, 150ms) var(--ease-out, ease);
}

.topnav-user-dropdown button:hover {
  background: var(--brand-primary-soft, #EEF2FF);
}

.topnav-user-dropdown button strong {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title, #0F172A);
}

.topnav-user-dropdown button span {
  font-size: 11px;
  color: var(--text-secondary, #64748B);
}

.topnav-user-dropdown button.danger strong {
  color: var(--error, #DC2626);
}

/* 主体容器：顶栏之下的全宽区域 */
.app-body {
  flex: 1 1 auto;
  min-width: 0;
  min-height: 0;
}

/* ===== 二级上下文条（非工作台页面显示） ===== */
.context-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex: 0 0 auto;
  height: 46px !important;
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid var(--border-light, #EEF2FF) !important;
}

.context-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.context-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-title, #111827);
  white-space: nowrap;
}

.context-subtitle {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--text-muted, #94A3B8);
}

.context-back {
  flex: 0 0 auto;
  height: 26px;
  padding: 0 11px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: 999px;
  background: #ffffff;
  color: var(--text-secondary, #475569);
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}

.context-back:hover {
  border-color: var(--brand-primary, #6366F1);
  background: var(--brand-primary-soft, #EEF2FF);
  color: var(--brand-primary, #6366F1);
}

.context-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.admin-login-button,
.feishu-login-button {
  height: 30px;
  padding: 0 14px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: 999px;
  background: var(--bg-card, #FFFFFF);
  color: var(--text-body, #374151);
  font-size: 12px;
  font-weight: 800;
  cursor: pointer;
  box-shadow: var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04));
  transition: all 0.2s ease;
}

.admin-login-button {
  border-color: var(--border, #E5E7EB);
  background: var(--bg-card, #FFFFFF);
  color: var(--text-body, #374151);
  box-shadow: var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04));
}

.admin-login-button:hover,
.feishu-login-button:hover:not(:disabled) {
  transform: translateY(-1px);
}

.feishu-login-button:hover:not(:disabled) {
  border-color: var(--border-hover, #D1D5DB);
  background: var(--bg-soft, #F3F4F6);
}

.admin-login-button:hover {
  border-color: var(--border-hover, #D1D5DB);
  background: var(--bg-soft, #F3F4F6);
}

.feishu-login-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}


.admin-console-float {
  position: fixed;
  z-index: 1200;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  touch-action: none;
}

.admin-console-float-main,
.admin-console-float-close {
  border: 1px solid var(--border, #E5E7EB);
  color: var(--text-title, #111827);
  background: var(--bg-card, #FFFFFF);
  box-shadow: var(--shadow-lg, 0 4px 8px rgba(0,0,0,0.03), 0 16px 40px rgba(0,0,0,0.07));
}

.admin-console-float-main {
  height: 44px;
  padding: 0 16px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 700;
  cursor: grab;
}

.admin-console-float-main.dragging {
  cursor: grabbing;
}

.admin-console-float-main .el-icon {
  width: 20px;
  height: 20px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  background: var(--brand-black, #1A1A1A);
}

.admin-console-float-close {
  width: 34px;
  height: 34px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.admin-console-float-main:hover,
.admin-console-float-close:hover {
  transform: translateY(-1px);
}

.admin-login-dialog {
  border-radius: 18px !important;
}

.admin-login-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.admin-login-field {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: var(--text-body, #374151);
  font-size: 13px;
  font-weight: 700;
}

.admin-login-field input {
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: var(--radius-sm, 8px);
  outline: none;
  color: var(--text-title, #111827);
  font-size: 14px;
  transition: all 0.18s ease;
}

.admin-login-field input:focus {
  border-color: var(--brand-primary, #6366F1);
  box-shadow: 0 0 0 3px var(--brand-primary-focus, rgba(99, 102, 241, 0.16));
}

.auth-password-button {
  height: 22px;
  padding: 0 8px;
  border: 0;
  border-radius: 999px;
  background: var(--bg-soft, #F3F4F6);
  color: var(--text-secondary, #6B7280);
  font-size: 11px;
  font-weight: 750;
  cursor: pointer;
}

.auth-password-button:hover {
  background: var(--border-light, #F3F4F6);
}

.password-dialog {
  border-radius: var(--radius-lg, 16px) !important;
  overflow: hidden;
  box-shadow: var(--shadow-xl, 0 8px 16px rgba(0,0,0,0.04), 0 24px 56px rgba(0,0,0,0.08)) !important;
}

.password-dialog .el-dialog__header {
  padding: 22px 28px 14px;
  margin: 0;
  border-bottom: 0;
}

.password-dialog .el-dialog__title {
  font-size: 18px;
  font-weight: 900;
  color: var(--text-title, #111827);
}

.password-dialog .el-dialog__body {
  padding: 8px 28px 24px;
}

.password-dialog .el-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 18px 28px 24px;
  border-top: 1px solid var(--border-light, #F3F4F6);
  background: var(--bg-card, #FFFFFF);
}

.password-panel {
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--brand-primary-soft, #EEF2FF);
  border-radius: var(--radius-md, 12px);
  background: var(--brand-primary-soft, #EEF2FF);
}

.password-panel-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-sm, 8px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--brand-black, #1A1A1A);
  color: #fff;
  font-size: 13px;
  font-weight: 900;
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.04));
}

.password-panel h3 {
  margin: 0;
  color: var(--text-title, #111827);
  font-size: 14px;
  font-weight: 900;
}

.password-panel p {
  margin: 6px 0 0;
  color: var(--text-secondary, #6B7280);
  font-size: 12px;
  line-height: 1.5;
}

.password-form {
  display: flex;
  flex-direction: column;
  gap: 13px;
}

.password-form label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  color: var(--text-body, #374151);
  font-size: 13px;
  font-weight: 800;
}

.password-form input {
  width: 100%;
  height: 40px;
  box-sizing: border-box;
  padding: 0 13px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: var(--radius-sm, 8px);
  outline: none;
  color: var(--text-title, #111827);
  font-size: 14px;
  background: var(--bg-card, #FFFFFF);
  transition: all 0.18s ease;
}

.dialog-password-control {
  position: relative;
}

.dialog-password-control input {
  padding-right: 44px;
}

.dialog-password-control input[type="password"] {
  font-size: 20px;
}

.dialog-password-control input::placeholder {
  font-size: 13px;
}

.dialog-password-eye {
  position: absolute;
  right: 6px;
  top: 50%;
  width: 30px;
  height: 30px;
  padding: 0;
  border: 0;
  border-radius: var(--radius-xs, 6px);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted, #9CA3AF);
  background: transparent;
  cursor: pointer;
  transition: all 0.18s ease;
  transform: translateY(-50%);
}

.dialog-password-eye:hover {
  color: var(--text-secondary, #6B7280);
  background: var(--bg-soft, #F3F4F6);
}

.dialog-password-eye .el-icon {
  font-size: 16px;
}

.password-form input:focus {
  border-color: var(--brand-primary, #6366F1);
  box-shadow: 0 0 0 3px var(--brand-primary-focus, rgba(99, 102, 241, 0.16));
}

.dialog-ghost-button,
.dialog-primary-button {
  min-width: 82px;
  height: 38px;
  padding: 0 18px;
  border-radius: 11px;
  font-size: 13px;
  font-weight: 800;
  cursor: pointer;
  transition: all 0.18s ease;
}

.dialog-ghost-button {
  border: 1px solid var(--border, #E5E7EB);
  background: var(--bg-card, #FFFFFF);
  color: var(--text-body, #374151);
}

.dialog-primary-button {
  border: 1px solid var(--brand-primary, #6366F1);
  background: var(--brand-primary, #6366F1);
  color: #fff;
  box-shadow: var(--shadow-sm, 0 1px 3px rgba(0,0,0,0.04));
}

.dialog-ghost-button:hover {
  border-color: var(--border-hover, #D1D5DB);
  background: var(--bg-soft, #F3F4F6);
}

.dialog-primary-button:hover {
  background: var(--brand-primary-hover, #4F46E5);
  border-color: var(--brand-primary-hover, #4F46E5);
}

.dialog-primary-button:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.app-toast-modern.el-message {
  min-width: 0;
  width: auto;
  max-width: min(360px, calc(100vw - 32px));
  padding: 9px 13px;
  border: 1px solid var(--border, #E5E7EB);
  border-radius: var(--radius-sm, 8px);
  background: var(--bg-card, #FFFFFF);
  box-shadow: var(--shadow-md, 0 2px 4px rgba(0,0,0,0.03), 0 8px 24px rgba(0,0,0,0.05));
  backdrop-filter: blur(10px);
}

.app-toast-modern .el-message__content {
  color: var(--text-title, #111827);
  font-size: 12px;
  font-weight: 760;
  line-height: 1.35;
}

.app-toast-modern .el-message__icon {
  margin-right: 8px;
  color: var(--brand-black, #1A1A1A);
  font-size: 14px;
}

.backend-status-chip {
  height: 26px;
  padding: 0 10px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  font-size: 12px;
  font-weight: 750;
  letter-spacing: 0.01em;
  border: 1px solid var(--border, #E5E7EB);
  background: var(--bg-card, #FFFFFF);
  color: var(--text-secondary, #6B7280);
  box-shadow: var(--shadow-xs, 0 1px 2px rgba(0,0,0,0.04));
}

.backend-status-chip.is-online {
  border-color: rgba(16, 185, 129, 0.24);
  background: var(--success-soft, #ECFDF5);
  color: var(--success, #10B981);
}

.backend-status-chip.is-offline {
  border-color: rgba(99, 102, 241, 0.2);
  background: var(--error-soft, #EEF2FF);
  color: var(--error, #6366F1);
}

.backend-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 14%, transparent);
}

.clock {
  font-variant-numeric: tabular-nums;
  color: var(--text-muted, #9CA3AF);
  font-size: 12px;
}

.page-wrap {
  padding: 0 24px 24px;
  overflow: auto;
  background: var(--bg-page, #EDF2F6);
}

.page-wrap-smart {
  /* 工作台全出血：内容区自行管padding，外壳不再留边 */
  padding: 0;
  overflow: hidden;
  display: flex;
  min-height: 0;
}

.page-wrap-smart > * {
  flex: 1;
  min-height: 0;
}

.page-wrap > * {
  animation: page-enter 0.28s ease;
}

.history-panel-enter-active,
.history-panel-leave-active {
  transition: all 0.2s ease;
}

.history-panel-enter-from,
.history-panel-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@keyframes page-enter {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ===== 全局命令面板（⌘K） ===== */
.command-palette-mask {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 12vh 20px 20px;
  background: rgba(15, 23, 42, 0.42);
  backdrop-filter: saturate(140%) blur(6px);
  -webkit-backdrop-filter: saturate(140%) blur(6px);
}

.command-palette {
  width: 100%;
  max-width: 560px;
  max-height: 60vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: var(--radius-xl, 20px);
  background: var(--bg-card, #FFFFFF);
  box-shadow: 0 32px 80px rgba(30, 27, 75, 0.35);
}

.command-palette-search {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border-light, #EEF2FF);
  background: var(--brand-gradient-soft, linear-gradient(135deg, #EEF2FF 0%, #EFF6FF 100%));
}

.command-palette-search-icon {
  flex: 0 0 auto;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 1.8px solid var(--brand-primary, #6366F1);
  position: relative;
}

.command-palette-search-icon::after {
  content: '';
  position: absolute;
  left: 12px;
  top: 12px;
  width: 7px;
  height: 2px;
  border-radius: 2px;
  background: var(--brand-primary, #6366F1);
  transform: rotate(45deg);
  transform-origin: left center;
}

.command-palette-input {
  flex: 1 1 auto;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  color: var(--text-title, #0F172A);
  font-size: 15px;
}

.command-palette-input::placeholder {
  color: var(--text-placeholder, #CBD5E1);
}

.command-palette-hint {
  flex: 0 0 auto;
  padding: 2px 8px;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  color: var(--text-muted, #94A3B8);
  font-size: 11px;
  letter-spacing: 0.02em;
}

.command-palette-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

.command-palette-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 10px 12px;
  border: 0;
  border-radius: var(--radius-md, 12px);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background var(--duration-fast, 150ms) var(--ease-out, ease);
}

.command-palette-item.is-active {
  background: var(--brand-primary-soft, #EEF2FF);
}

.command-palette-item-icon {
  flex: 0 0 auto;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--brand-gradient-soft, linear-gradient(135deg, #EEF2FF 0%, #EFF6FF 100%));
  color: var(--brand-primary, #6366F1);
  font-size: 16px;
}

.command-palette-item.is-active .command-palette-item-icon {
  background: var(--brand-gradient, linear-gradient(135deg, #6366F1 0%, #3B82F6 100%));
  color: #ffffff;
}

.command-palette-item-body {
  display: flex;
  flex-direction: column;
  gap: 1px;
  min-width: 0;
}

.command-palette-item-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-title, #0F172A);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.command-palette-item-path {
  font-family: var(--font-mono, monospace);
  font-size: 11px;
  color: var(--text-muted, #94A3B8);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.command-palette-empty {
  padding: 26px 12px;
  text-align: center;
  color: var(--text-muted, #94A3B8);
  font-size: 13px;
}

/* 面板/菜单过渡动画 */
.palette-fade-enter-active,
.palette-fade-leave-active {
  transition: opacity 0.2s ease;
}

.palette-fade-enter-active .command-palette,
.palette-fade-leave-active .command-palette {
  transition: transform 0.22s var(--ease-out, cubic-bezier(0.16, 1, 0.3, 1));
}

.palette-fade-enter-from,
.palette-fade-leave-to {
  opacity: 0;
}

.palette-fade-enter-from .command-palette,
.palette-fade-leave-to .command-palette {
  transform: translateY(-12px) scale(0.98);
}

.user-menu-rise-enter-active,
.user-menu-rise-leave-active {
  transition: opacity 0.18s ease, transform 0.18s var(--ease-out, cubic-bezier(0.16, 1, 0.3, 1));
}

.user-menu-rise-enter-from,
.user-menu-rise-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 1180px) {
  .topnav-brand-env {
    display: none;
  }

  .topnav-command {
    width: 150px;
  }

  .topnav-user-meta {
    display: none;
  }

  .topnav-user-chip {
    padding: 0 10px 0 4px;
  }
}

@media (max-width: 900px) {
  .app-topnav {
    gap: 10px;
    padding: 0 12px;
  }

  .topnav-brand-name {
    display: none;
  }

  .topnav-command {
    width: auto;
  }

  .topnav-command-text {
    display: none;
  }

  .topnav-history-label {
    display: none;
  }

  .topnav-history {
    padding: 0 10px;
  }

  .topnav-menu .el-menu-item span,
  .topnav-menu .el-sub-menu__title span {
    display: none;
  }

  .topnav-menu.el-menu--horizontal > .el-menu-item,
  .topnav-menu.el-menu--horizontal > .el-sub-menu > .el-sub-menu__title {
    padding: 0 10px !important;
  }

  .topnav-menu .el-menu-item .el-icon,
  .topnav-menu .el-sub-menu__title .el-icon {
    margin-right: 0;
  }
}
</style>

