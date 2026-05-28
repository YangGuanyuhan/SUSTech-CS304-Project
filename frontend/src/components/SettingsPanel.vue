<template>
  <section class="settings-panel">
    <header class="settings-header">
      <div class="header-title">
        <p class="eyebrow">运行设置</p>
        <h2>服务与工具配置中心</h2>
        <p class="header-copy">左侧选择配置分组，右侧只展示当前分组的设置内容。</p>
      </div>
      <div class="header-actions">
        <span class="badge" :class="{ ready: state.api_key_configured || bbState.password_configured }">
          {{ state.api_key_configured || bbState.password_configured ? "部分已就绪" : "等待配置" }}
        </span>
        <button type="button" class="collapse-btn" @click="navCollapsed = !navCollapsed">
          {{ navCollapsed ? "展开导航" : "折叠导航" }}
        </button>
        <button type="button" class="close-btn" @click="$emit('close')">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
          关闭
        </button>
      </div>
    </header>

    <div class="settings-layout">
      <aside :class="['settings-nav', { collapsed: navCollapsed }]">
        <button
          v-for="item in sections"
          :key="item.id"
          type="button"
          :class="['nav-item', { active: activeSection === item.id }]"
          @click="activeSection = item.id"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span v-if="!navCollapsed" class="nav-copy">
            <strong>{{ item.label }}</strong>
            <small>{{ item.description }}</small>
          </span>
        </button>
      </aside>

      <div class="settings-content">
        <template v-if="activeSection === 'llm'">
          <section class="content-panel hero-panel">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">LLM</p>
                <h3>模型与网关配置</h3>
              </div>
              <span class="badge" :class="{ ready: state.api_key_configured }">
                {{ state.api_key_configured ? "已加载密钥" : "缺少密钥" }}
              </span>
            </div>
            <p class="hint">
              API 密钥仅发送到后端并存储在服务器内存中，不会返回浏览器。服务重启后需要重新注入。
            </p>

            <div class="status-grid">
              <article class="status-card">
                <span>当前提供商</span>
                <strong>{{ state.provider || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>当前模型</span>
                <strong>{{ state.model || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>Base URL</span>
                <strong>{{ state.base_url || "默认地址" }}</strong>
              </article>
              <article class="status-card">
                <span>推理模式</span>
                <strong>{{ state.enable_reasoning ? "已启用" : "已禁用" }}</strong>
              </article>
            </div>
          </section>

          <section class="content-panel">
            <div class="section-top">
              <div>
                <strong>已保存的 LLM 配置</strong>
                <p class="hint compact">保存 provider、model、Base URL 等非敏感字段，便于快速切换。</p>
              </div>
              <button type="button" :disabled="saving" @click="openLLMEditorForCreate">新建配置</button>
            </div>

            <div v-if="profiles.length" class="profile-list">
              <article v-for="profile in profiles" :key="profile.name" class="profile-item">
                <div class="profile-info">
                  <strong>{{ profile.name }}</strong>
                  <p>{{ profile.provider }} / {{ profile.model }}</p>
                  <small>{{ profile.base_url || "使用默认 Base URL" }}</small>
                </div>
                <div class="profile-actions">
                  <button type="button" class="apply-btn" :disabled="saving" @click="useProfile(profile)">应用</button>
                  <button type="button" class="secondary action-btn" :disabled="saving" @click="openLLMEditorForEdit(profile)">编辑</button>
                  <button type="button" class="delete-btn" :disabled="saving" @click="removeProfile(profile.name)">删除</button>
                </div>
              </article>
            </div>
            <p v-else class="hint compact">暂无保存的配置。</p>

            <div class="actions inline-actions panel-actions">
              <button type="button" class="secondary" :disabled="saving" @click="refresh">刷新运行时</button>
              <button type="button" class="secondary" :disabled="saving" @click="testConnection">测试连接</button>
            </div>
          </section>

          <section v-if="llmEditorOpen" class="content-panel editor-panel">
            <div class="section-top">
              <div>
                <strong>{{ llmEditorMode === "create" ? "新增 LLM 配置" : "编辑 LLM 配置" }}</strong>
                <p class="hint compact">填写后可保存为配置，也可直接应用到当前运行时。</p>
              </div>
              <button type="button" class="secondary" :disabled="saving" @click="closeLLMEditor">收起</button>
            </div>

            <form class="config-form" @submit.prevent="save">
              <label class="full">
                <span>配置名称</span>
                <input v-model="form.profile_name" placeholder="例如: openai-main 或 deepseek-gateway" autocomplete="off" />
              </label>
              <label>
                <span>提供商</span>
                <select v-model="form.provider">
                  <option value="openai">OpenAI</option>
                  <option value="anthropic">Anthropic</option>
                  <option value="deepseek">DeepSeek</option>
                  <option value="azure">Azure OpenAI</option>
                </select>
              </label>
              <label>
                <span>模型</span>
                <input v-model="form.model" placeholder="例如: gpt-4o-mini" autocomplete="off" />
              </label>
              <label class="full">
                <span>Base URL</span>
                <input v-model="form.base_url" placeholder="https://api.openai.com/v1" autocomplete="off" />
              </label>
              <label class="full">
                <span>API 密钥</span>
                <input
                  v-model="form.api_key"
                  type="password"
                  placeholder="留空以保持当前密钥"
                  autocomplete="new-password"
                />
              </label>
              <label class="toggle-label full">
                <span class="toggle-row">
                  <span>启用推理模式 (DeepSeek R1 等推理模型)</span>
                  <input v-model="form.enable_reasoning" type="checkbox" class="toggle-input" />
                </span>
              </label>
              <div class="actions full">
                <button type="button" class="secondary" :disabled="saving" @click="saveProfile">
                  {{ saving ? "保存中..." : "保存到列表" }}
                </button>
                <button type="submit" :disabled="saving">{{ saving ? "保存中..." : "应用到运行时" }}</button>
              </div>
            </form>
          </section>
        </template>

        <template v-else-if="activeSection === 'bb'">
          <section class="content-panel hero-panel bb-hero">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Blackboard</p>
                <h3>课程系统登录配置</h3>
              </div>
              <span class="badge" :class="{ ready: bbState.password_configured }">
                {{ bbState.password_configured ? "已配置密码" : "未配置密码" }}
              </span>
            </div>
            <p class="hint">
              这里用于配置 Blackboard 登录信息，供课程同步和日历拉取使用。密码只存在后端运行时内存。
            </p>

            <div class="status-grid">
              <article class="status-card">
                <span>当前学号</span>
                <strong>{{ bbState.student_id || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>Base URL</span>
                <strong>{{ bbState.base_url || "默认地址" }}</strong>
              </article>
              <article class="status-card">
                <span>密码状态</span>
                <strong>{{ bbState.password_configured ? "已存在" : "待输入" }}</strong>
              </article>
            </div>
          </section>

          <section class="content-panel">
            <div class="section-top">
              <div>
                <strong>已保存的 Blackboard 配置</strong>
                <p class="hint compact">保存学号和地址，密码会加密存储，方便切换不同账户。</p>
              </div>
              <button type="button" :disabled="saving" @click="openBBEditorForCreate">新建配置</button>
            </div>

            <div v-if="bbProfiles.length" class="profile-list">
              <article v-for="profile in bbProfiles" :key="profile.name" class="profile-item">
                <div class="profile-info">
                  <strong>{{ profile.name }}</strong>
                  <p>{{ profile.student_id }}</p>
                  <small>{{ profile.base_url || "使用默认 Base URL" }}</small>
                </div>
                <div class="profile-actions">
                  <button type="button" class="apply-btn" :disabled="saving" @click="useBBProfile(profile)">应用</button>
                  <button type="button" class="secondary action-btn" :disabled="saving" @click="openBBEditorForEdit(profile)">编辑</button>
                  <button type="button" class="delete-btn" :disabled="saving" @click="removeBBProfile(profile.name)">删除</button>
                </div>
              </article>
            </div>
            <p v-else class="hint compact">暂无保存的配置。</p>

            <div class="actions inline-actions panel-actions">
              <button type="button" class="secondary" :disabled="saving" @click="refreshBlackboard">刷新运行时</button>
              <button type="button" class="secondary" :disabled="saving" @click="testBlackboard">测试连接</button>
            </div>
          </section>

          <section v-if="bbEditorOpen" class="content-panel editor-panel">
            <div class="section-top">
              <div>
                <strong>{{ bbEditorMode === "create" ? "新增 Blackboard 配置" : "编辑 Blackboard 配置" }}</strong>
                <p class="hint compact">填写后可保存为配置，也可直接应用到当前运行时。</p>
              </div>
              <button type="button" class="secondary" :disabled="saving" @click="closeBBEditor">收起</button>
            </div>

            <form class="bb-form" @submit.prevent="saveBlackboard">
              <label class="full">
                <span>配置名称</span>
                <input v-model="bbForm.profile_name" placeholder="例如: bb-main" autocomplete="off" />
              </label>
              <label class="full">
                <span>学号</span>
                <input v-model="bbForm.student_id" placeholder="你的学号" autocomplete="off" />
              </label>
              <label class="full">
                <span>CAS 密码</span>
                <input
                  v-model="bbForm.password"
                  type="password"
                  placeholder="留空以保持当前密码"
                  autocomplete="new-password"
                />
              </label>
              <label class="full">
                <span>Base URL（可选）</span>
                <input v-model="bbForm.base_url" placeholder="https://bb.sustech.edu.cn" autocomplete="off" />
              </label>
              <div class="actions full">
                <button type="button" class="secondary" :disabled="saving" @click="saveBBProfile">
                  {{ saving ? "保存中..." : "保存到列表" }}
                </button>
                <button type="submit" :disabled="saving">{{ saving ? "保存中..." : "应用到运行时" }}</button>
              </div>
            </form>
          </section>
        </template>

        <template v-else-if="activeSection === 'email'">
          <section class="content-panel hero-panel email-hero">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Email</p>
                <h3>SMTP 邮件服务配置</h3>
              </div>
              <span class="badge" :class="{ ready: emailState.password_configured }">
                {{ emailState.password_configured ? "已配置密码" : "未配置密码" }}
              </span>
            </div>
            <p class="hint">
              配置 SMTP 服务器信息，用于邮件通知和测试连接。密码只存在后端运行时内存。
            </p>

            <div class="status-grid">
              <article class="status-card">
                <span>SMTP 服务器</span>
                <strong>{{ emailState.smtp_host || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>端口</span>
                <strong>{{ emailState.smtp_port }}</strong>
              </article>
              <article class="status-card">
                <span>用户名</span>
                <strong>{{ emailState.smtp_user || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>加密方式</span>
                <strong>{{ emailState.smtp_encryption?.toUpperCase() || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>IMAP 服务器</span>
                <strong>{{ emailState.imap_host || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>密码状态</span>
                <strong>{{ emailState.password_configured ? "已存在" : "待输入" }}</strong>
              </article>
            </div>
          </section>

          <section class="content-panel">
            <div class="section-top">
              <div>
                <strong>已保存的 Email 配置</strong>
                <p class="hint compact">保存 SMTP/IMAP 服务器和账户信息，密码会加密存储，方便切换不同邮箱。</p>
              </div>
              <button type="button" :disabled="saving" @click="openEmailEditorForCreate">新建配置</button>
            </div>

            <div v-if="emailProfiles.length" class="profile-list">
              <article v-for="profile in emailProfiles" :key="profile.name" class="profile-item">
                <div class="profile-info">
                  <strong>{{ profile.name }}</strong>
                  <p>{{ profile.smtp_user }} / {{ profile.smtp_host }}:{{ profile.smtp_port }}</p>
                  <small>{{ profile.smtp_encryption?.toUpperCase() }} | IMAP: {{ profile.imap_host }}:{{ profile.imap_port }}</small>
                </div>
                <div class="profile-actions">
                  <button type="button" class="apply-btn" :disabled="saving" @click="useEmailProfile(profile)">应用</button>
                  <button type="button" class="secondary action-btn" :disabled="saving" @click="openEmailEditorForEdit(profile)">编辑</button>
                  <button type="button" class="delete-btn" :disabled="saving" @click="removeEmailProfile(profile.name)">删除</button>
                </div>
              </article>
            </div>
            <p v-else class="hint compact">暂无保存的配置。</p>

            <div class="actions inline-actions panel-actions">
              <button type="button" class="secondary" :disabled="saving" @click="refreshEmail">刷新运行时</button>
              <button type="button" class="secondary" :disabled="saving" @click="testEmail">测试连接</button>
            </div>
          </section>

          <section v-if="emailEditorOpen" class="content-panel editor-panel">
            <div class="section-top">
              <div>
                <strong>{{ emailEditorMode === "create" ? "新增 Email 配置" : "编辑 Email 配置" }}</strong>
                <p class="hint compact">填写后可保存为配置，也可直接应用到当前运行时。</p>
              </div>
              <button type="button" class="secondary" :disabled="saving" @click="closeEmailEditor">收起</button>
            </div>

            <form class="config-form" @submit.prevent="saveEmail">
              <label class="full">
                <span>配置名称</span>
                <input v-model="emailForm.profile_name" placeholder="例如: sustech-mail" autocomplete="off" />
              </label>
              <label>
                <span>SMTP 服务器地址</span>
                <input v-model="emailForm.smtp_host" placeholder="smtp.exmail.qq.com" autocomplete="off" />
              </label>
              <label>
                <span>SMTP 端口</span>
                <input v-model.number="emailForm.smtp_port" type="number" placeholder="465" />
              </label>
              <label class="full">
                <span>用户名 (邮箱地址)</span>
                <input v-model="emailForm.smtp_user" placeholder="12345678@mail.sustech.edu.cn" autocomplete="off" />
              </label>
              <label class="full">
                <span>密码 / 授权码</span>
                <input
                  v-model="emailForm.password"
                  type="password"
                  placeholder="留空以保持当前密码"
                  autocomplete="new-password"
                />
              </label>
              <label>
                <span>加密方式</span>
                <select v-model="emailForm.smtp_encryption">
                  <option value="ssl">SSL</option>
                  <option value="tls">TLS (STARTTLS)</option>
                  <option value="none">无加密</option>
                </select>
              </label>
              <label>
                <span>IMAP 服务器地址</span>
                <input v-model="emailForm.imap_host" placeholder="imap.exmail.qq.com" autocomplete="off" />
              </label>
              <label>
                <span>IMAP 端口</span>
                <input v-model.number="emailForm.imap_port" type="number" placeholder="993" />
              </label>
              <div class="actions full">
                <button type="button" class="secondary" :disabled="saving" @click="saveEmailProfileToDb">
                  {{ saving ? "保存中..." : "保存到列表" }}
                </button>
                <button type="submit" :disabled="saving">{{ saving ? "保存中..." : "应用到运行时" }}</button>
              </div>
            </form>
          </section>
        </template>

        <template v-else-if="activeSection === 'search'">
          <section class="content-panel hero-panel search-hero">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Web Search</p>
                <h3>联网搜索配置</h3>
              </div>
              <span class="badge" :class="{ ready: searchState.api_key_configured }">
                {{ searchState.api_key_configured ? "已配置" : "未配置" }}
              </span>
            </div>
            <p class="hint">
              选择 Agent 使用的搜索提供商。Mock 用于本地调试，Brave 和 Bocha 需要各自的 API 密钥。
            </p>

            <div class="status-grid">
              <article class="status-card">
                <span>当前提供商</span>
                <strong>{{ searchState.provider || "未设置" }}</strong>
              </article>
              <article class="status-card">
                <span>密钥状态</span>
                <strong>{{ searchState.api_key_configured ? "已存在" : "待输入" }}</strong>
              </article>
              <article class="status-card">
                <span>超时</span>
                <strong>{{ searchState.timeout }}s</strong>
              </article>
            </div>
          </section>

          <section class="content-panel editor-panel">
            <div class="section-top">
              <div>
                <strong>搜索运行时</strong>
                <p class="hint compact">保存后立即影响 web_search 工具。API 密钥不会返回到浏览器。</p>
              </div>
            </div>

            <form class="config-form" @submit.prevent="saveSearch">
              <label>
                <span>提供商</span>
                <select v-model="searchForm.provider">
                  <option value="mock">Mock 调试</option>
                  <option value="bocha">Bocha 博查</option>
                  <option value="brave">Brave Search</option>
                </select>
              </label>
              <label>
                <span>超时秒数</span>
                <input v-model.number="searchForm.timeout" type="number" min="1" max="120" />
              </label>
              <label class="full">
                <span>API 密钥</span>
                <input
                  v-model="searchForm.api_key"
                  type="password"
                  :placeholder="searchForm.provider === 'mock' ? 'Mock 不需要密钥' : '留空以保持当前密钥'"
                  autocomplete="new-password"
                />
              </label>
              <label class="toggle-label full">
                <span class="toggle-row">
                  <span>清空当前提供商的密钥</span>
                  <input v-model="searchForm.replace_api_key" type="checkbox" class="toggle-input" />
                </span>
              </label>
              <div class="actions full">
                <button type="button" class="secondary" :disabled="saving" @click="refreshSearch">刷新</button>
                <button type="button" class="secondary" :disabled="saving" @click="testSearch">测试连接</button>
                <button type="submit" :disabled="saving">{{ saving ? "保存中..." : "应用搜索配置" }}</button>
              </div>
            </form>
          </section>
        </template>

        <template v-else-if="activeSection === 'skills'">
          <section class="content-panel hero-panel">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Skills</p>
                <h3>Agent Skills</h3>
              </div>
              <span class="badge" :class="{ ready: skillList.length > 0 }">
                {{ skillList.length ? skillList.length + " 个可用" : "未发现" }}
              </span>
            </div>
            <p class="hint">
              后端会扫描仓库和用户目录下的 .agents/skills，只把元数据注入 Agent，需要时再读取 SKILL.md。
            </p>
          </section>

          <section class="content-panel">
            <div class="section-top">
              <div>
                <strong>已发现的 Skills</strong>
                <p class="hint compact">禁用或解析失败的 skill 会显示错误，不会被 Agent 使用。</p>
              </div>
              <button type="button" class="secondary" :disabled="saving" @click="refreshSkills">刷新</button>
            </div>
            <div v-if="skillList.length" class="profile-list">
              <article v-for="skill in skillList" :key="`${skill.name}-${skill.path}`" class="profile-item">
                <div class="profile-info">
                  <strong>{{ skill.name }}</strong>
                  <p>{{ skill.description || skill.error || "无描述" }}</p>
                  <small>{{ skill.scope }} · {{ skill.path }}</small>
                </div>
                <span class="badge" :class="{ ready: skill.enabled }">
                  {{ skill.enabled ? (skill.allow_implicit_invocation ? "自动可用" : "仅显式") : "不可用" }}
                </span>
              </article>
            </div>
            <p v-else class="hint compact">暂无可用 skill。可在仓库或用户目录创建 .agents/skills/&lt;name&gt;/SKILL.md。</p>
          </section>
        </template>

        <template v-else-if="activeSection === 'mcp'">
          <section class="content-panel hero-panel">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">MCP</p>
                <h3>MCP Server 配置</h3>
              </div>
              <span class="badge" :class="{ ready: mcpServers.some((server) => server.enabled) }">
                {{ mcpServers.some((server) => server.enabled) ? "已启用" : "未启用" }}
              </span>
            </div>
            <p class="hint">
              配置会保存在后端运行时内存中。启用后，Agent 会把 MCP server 暴露的工具作为带前缀的工具使用。
            </p>
          </section>

          <section class="content-panel">
            <div class="section-top">
              <div>
                <strong>Server 列表</strong>
                <p class="hint compact">保存、删除会立即应用到后端运行时。后端重启后需要重新配置。</p>
              </div>
              <button type="button" :disabled="saving" @click="openMCPCreate">新增 Server</button>
            </div>
            <div v-if="mcpServers.length" class="profile-list">
              <article v-for="server in mcpServers" :key="server.id" class="profile-item mcp-server-card">
                <div class="profile-info">
                  <div class="mcp-title-row">
                    <strong>{{ server.id }}</strong>
                    <span class="transport-pill">{{ server.transport }}</span>
                  </div>
                  <p>工具前缀: {{ server.tool_prefix || server.id }}</p>
                  <small>{{ server.transport === "stdio" ? server.command : server.url }}</small>
                </div>
                <div class="profile-actions">
                  <button type="button" class="secondary action-btn" :disabled="saving" @click="editMCPServer(server)">编辑</button>
                  <button type="button" class="secondary action-btn" :disabled="saving" @click="testMCPServer(server)">测试</button>
                  <button type="button" class="delete-btn" :disabled="saving" @click="removeMCPServer(server.id)">删除</button>
                </div>
              </article>
            </div>
            <p v-else class="hint compact">暂无 MCP server 配置。</p>
            <div class="actions inline-actions panel-actions">
              <button type="button" class="secondary" :disabled="saving" @click="refreshMCP">刷新</button>
              <button type="button" :disabled="saving" @click="saveMCPConfig">重新应用当前列表</button>
            </div>
          </section>

          <section v-if="mcpEditorOpen" class="content-panel editor-panel">
            <div class="section-top">
              <div>
                <strong>{{ mcpEditorMode === "create" ? "新增 MCP Server" : "编辑 MCP Server" }}</strong>
                <p class="hint compact">{{ mcpForm.transport === "stdio" ? "环境变量是选填项；按字段名和值逐行添加。" : "请求头是选填项；常见字段如 Authorization，值如 Bearer token。" }}</p>
              </div>
              <button type="button" class="secondary" :disabled="saving" @click="mcpEditorOpen = false">收起</button>
            </div>
            <form class="config-form" @submit.prevent="upsertMCPServer">
              <label>
                <span>Server ID</span>
                <input v-model="mcpForm.id" :disabled="mcpEditorMode === 'edit'" placeholder="例如: filesystem" autocomplete="off" />
              </label>
              <label>
                <span>Transport</span>
                <select v-model="mcpForm.transport">
                  <option value="stdio">stdio</option>
                  <option value="streamable_http">streamable_http</option>
                  <option value="sse">sse</option>
                </select>
              </label>
              <label>
                <span>工具前缀</span>
                <input v-model="mcpForm.tool_prefix" placeholder="默认使用 Server ID" autocomplete="off" />
              </label>
              <label class="toggle-label">
                <span class="toggle-row">
                  <span>启用</span>
                  <input v-model="mcpForm.enabled" type="checkbox" class="toggle-input" />
                </span>
              </label>
              <label v-if="mcpForm.transport === 'stdio'" class="full">
                <span>Command</span>
                <input v-model="mcpForm.command" placeholder="npx 或 python" autocomplete="off" />
              </label>
              <label v-if="mcpForm.transport === 'stdio'" class="full">
                <span>Args（每行一个）</span>
                <textarea v-model="mcpForm.argsText" rows="3" placeholder="-y&#10;@modelcontextprotocol/server-filesystem&#10;/path/to/root"></textarea>
              </label>
              <label v-if="mcpForm.transport !== 'stdio'" class="full">
                <span>URL</span>
                <input v-model="mcpForm.url" placeholder="https://example.com/mcp" autocomplete="off" />
              </label>
              <div class="full key-value-editor">
                <div class="key-value-top">
                  <div>
                    <strong>{{ mcpForm.transport === "stdio" ? "环境变量" : "请求头" }}</strong>
                    <p class="hint compact">{{ mcpForm.transport === "stdio" ? "例如 MCP_API_KEY = 21ND。" : "例如 Authorization = Bearer 21ND。" }}</p>
                  </div>
                  <button type="button" class="secondary" :disabled="saving" @click="addMCPPair">
                    新增字段
                  </button>
                </div>
                <div v-if="mcpForm.pairs.length" class="key-value-rows">
                  <div v-for="(pair, index) in mcpForm.pairs" :key="index" class="key-value-row">
                    <input v-model="pair.key" placeholder="字段名" autocomplete="off" />
                    <input v-model="pair.value" placeholder="内容" autocomplete="off" />
                    <button type="button" class="delete-btn icon-btn" :disabled="saving" @click="removeMCPPair(index)">删除</button>
                  </div>
                </div>
                <p v-else class="hint compact">没有额外字段；这是允许的。</p>
              </div>
              <div class="actions full">
                <button type="button" class="secondary" :disabled="saving" @click="testMCPForm">测试当前配置</button>
                <button type="submit" :disabled="saving">{{ saving ? "保存中..." : "保存并应用" }}</button>
              </div>
            </form>
          </section>
        </template>

        <template v-else-if="activeSection === 'backend'">
          <section class="content-panel hero-panel backend-hero">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Backend</p>
                <h3>后端服务状态</h3>
              </div>
              <span class="badge" :class="{ ready: backendStatus.healthy }">
                {{ backendStatus.healthy ? "服务在线" : "等待检测" }}
              </span>
            </div>
            <p class="hint">
              这一栏集中展示前端当前连接的后端地址、健康状态，以及依赖它的运行配置摘要。
            </p>
          </section>

          <section class="content-panel">
            <div class="status-grid backend-grid">
              <article class="status-card wide">
                <span>API Base</span>
                <strong>{{ backendBaseUrl }}</strong>
                <small>前端所有设置、聊天、课程与日程请求都通过这个入口访问后端。</small>
              </article>
              <article class="status-card">
                <span>健康状态</span>
                <strong>{{ backendStatus.healthy ? "Healthy" : "Unknown" }}</strong>
                <small>{{ backendStatus.message }}</small>
              </article>
              <article class="status-card">
                <span>LLM 运行时</span>
                <strong>{{ state.provider }} / {{ state.model }}</strong>
                <small>{{ state.api_key_configured ? "已注入密钥" : "缺少密钥" }}</small>
              </article>
              <article class="status-card">
                <span>Blackboard 运行时</span>
                <strong>{{ bbState.student_id || "未设置账号" }}</strong>
                <small>{{ bbState.password_configured ? "密码可用" : "密码未配置" }}</small>
              </article>
            </div>

            <div class="actions inline-actions">
              <button type="button" class="secondary" :disabled="saving" @click="checkBackendHealth">检查健康状态</button>
              <button type="button" class="secondary" :disabled="saving" @click="refreshAll">刷新全部设置</button>
            </div>
          </section>
        </template>

        <template v-else-if="activeSection === 'dev'">
          <section class="content-panel hero-panel developer-panel">
            <div class="panel-heading">
              <div>
                <p class="eyebrow">Developer</p>
                <h3>开发者工具</h3>
              </div>
              <span class="badge" :class="{ ready: showDeveloperTools }">
                {{ showDeveloperTools ? "开发模式" : "生产模式" }}
              </span>
            </div>
            <p class="hint">
              集中放调试入口，避免和运行配置混在一起。如果不是本地开发环境，这里会保持只读提示。
            </p>
          </section>

          <section class="content-panel">
            <div v-if="showDeveloperTools" class="dev-actions">
              <article class="dev-card">
                <div>
                  <strong>数据库视图</strong>
                  <p>打开后端数据库概览，用于课程演示和本地调试。</p>
                </div>
                <button type="button" :disabled="saving" @click="$emit('open-database-overview')">打开数据库视图</button>
              </article>

              <article class="dev-card">
                <div>
                  <strong>运行时刷新</strong>
                  <p>同步检查后端状态、LLM 配置和 Blackboard 配置，确认当前页面状态没有过期。</p>
                </div>
                <button type="button" :disabled="saving" @click="refreshAll">执行刷新</button>
              </article>
            </div>
            <p v-else class="hint">当前不是开发模式，开发者工具已隐藏。</p>
          </section>
        </template>

      </div>
    </div>

    <transition name="toast-fade">
      <p v-if="message" class="result" :class="{ error: messageType === 'error' }">{{ message }}</p>
    </transition>
  </section>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import {
  applyBBProfile,
  applyLLMProfile,
  deleteBBProfile,
  deleteLLMProfile,
  applyEmailProfile,
  deleteEmailProfile,
  getBBProfiles,
  getBlackboardSettings,
  getEmailProfiles,
  getEmailSettings,
  getHealth,
  getLLMProfiles,
  getLLMSettings,
  getMCPSettings,
  getSearchSettings,
  refreshSkillSettings,
  saveBBProfile as saveBBProfileAPI,
  saveEmailProfile,
  saveLLMProfile,
  testBlackboardSettings,
  testEmailSettings,
  testLLMSettings,
  testMCPSettings,
  testSearchSettings,
  updateBlackboardSettings,
  updateEmailSettings,
  updateLLMSettings,
  updateMCPSettings,
  updateSearchSettings
} from "../api/client";

defineEmits(["close", "open-database-overview"]);

const showDeveloperTools = import.meta.env.DEV;
const backendBaseUrl = "http://127.0.0.1:8000/api";
const navCollapsed = ref(false);
const activeSection = ref("llm");
const llmEditorOpen = ref(false);
const llmEditorMode = ref("create");
const bbEditorOpen = ref(false);
const bbEditorMode = ref("create");
const saving = ref(false);
const message = ref("");
const messageType = ref("info");
const profiles = ref([]);
const bbProfiles = ref([]);
let messageTimer = null;

const sections = [
  { id: "llm", label: "LLM 后端", description: "模型、网关与密钥", icon: "AI" },
  { id: "bb", label: "Blackboard", description: "课程系统登录", icon: "BB" },
  { id: "email", label: "Email 邮箱", description: "SMTP 邮件服务", icon: "@@" },
  { id: "search", label: "Web Search", description: "搜索提供商与密钥", icon: "SE" },
  { id: "skills", label: "Skills", description: "工作流能力扩展", icon: "SK" },
  { id: "mcp", label: "MCP", description: "外部工具服务器", icon: "MP" },
  { id: "backend", label: "后端服务", description: "状态与联通性", icon: "BE" },
  { id: "dev", label: "开发者工具", description: "数据库与调试入口", icon: "DV" }
];

const backendStatus = reactive({
  healthy: false,
  message: "尚未检测"
});

const state = reactive({
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key_configured: false,
  enable_reasoning: true
});

const bbState = reactive({
  student_id: "",
  base_url: "",
  password_configured: false
});

const form = reactive({
  profile_name: "",
  provider: "openai",
  model: "gpt-4o-mini",
  base_url: "",
  api_key: "",
  enable_reasoning: true
});

const bbForm = reactive({
  profile_name: "",
  student_id: "",
  password: "",
  base_url: "",
  replace_password: false
});

const emailState = reactive({
  smtp_host: "smtp.exmail.qq.com",
  smtp_port: 465,
  smtp_user: "",
  smtp_encryption: "ssl",
  imap_host: "imap.exmail.qq.com",
  imap_port: 993,
  password_configured: false
});

const emailForm = reactive({
  profile_name: "",
  smtp_host: "smtp.exmail.qq.com",
  smtp_port: 465,
  smtp_user: "",
  smtp_encryption: "ssl",
  imap_host: "imap.exmail.qq.com",
  imap_port: 993,
  password: "",
  replace_password: false
});

const searchState = reactive({
  provider: "mock",
  api_key_configured: false,
  timeout: 30
});

const searchForm = reactive({
  provider: "mock",
  api_key: "",
  replace_api_key: false,
  timeout: 30
});

const skillList = ref([]);
const mcpServers = ref([]);
const mcpEditorOpen = ref(false);
const mcpEditorMode = ref("create");
const mcpForm = reactive({
  id: "",
  enabled: true,
  transport: "stdio",
  tool_prefix: "",
  command: "",
  argsText: "",
  url: "",
  pairs: []
});

const emailEditorOpen = ref(false);
const emailEditorMode = ref("create");
const emailProfiles = ref([]);

function clearMessage() {
  message.value = "";
  if (messageTimer) {
    clearTimeout(messageTimer);
    messageTimer = null;
  }
}

function showMessage(text, type = "info") {
  message.value = text;
  messageType.value = type;
  if (messageTimer) {
    clearTimeout(messageTimer);
  }
  messageTimer = window.setTimeout(() => {
    message.value = "";
    messageTimer = null;
  }, 3000);
}

function applyState(payload) {
  state.provider = payload.provider;
  state.model = payload.model;
  state.base_url = payload.base_url ?? "";
  state.api_key_configured = Boolean(payload.api_key_configured);
  state.enable_reasoning = Boolean(payload.enable_reasoning);
  form.provider = payload.provider;
  form.model = payload.model;
  form.base_url = payload.base_url ?? "";
  form.enable_reasoning = Boolean(payload.enable_reasoning);
  form.api_key = "";
}

function closeLLMEditor() {
  llmEditorOpen.value = false;
}

function openLLMEditorForCreate() {
  llmEditorMode.value = "create";
  llmEditorOpen.value = true;
  form.profile_name = "";
  form.provider = "openai";
  form.model = "gpt-4o-mini";
  form.base_url = "";
  form.api_key = "";
}

function openLLMEditorForEdit(profile) {
  llmEditorMode.value = "edit";
  llmEditorOpen.value = true;
  form.profile_name = profile.name;
  form.provider = profile.provider;
  form.model = profile.model;
  form.base_url = profile.base_url ?? "";
  form.api_key = "";
}

function applyBBState(payload) {
  bbState.student_id = payload.student_id ?? "";
  bbState.base_url = payload.base_url ?? "";
  bbState.password_configured = Boolean(payload.password_configured);
  bbForm.student_id = payload.student_id ?? "";
  bbForm.base_url = payload.base_url ?? "";
  bbForm.password = "";
  bbForm.replace_password = false;
}

function applySearchState(payload) {
  searchState.provider = payload.provider ?? "mock";
  searchState.api_key_configured = Boolean(payload.api_key_configured);
  searchState.timeout = payload.timeout ?? 30;
  searchForm.provider = payload.provider ?? "mock";
  searchForm.api_key = "";
  searchForm.replace_api_key = false;
  searchForm.timeout = payload.timeout ?? 30;
}

function closeBBEditor() {
  bbEditorOpen.value = false;
}

function openBBEditorForCreate() {
  bbEditorMode.value = "create";
  bbEditorOpen.value = true;
  bbForm.profile_name = "";
  bbForm.student_id = "";
  bbForm.password = "";
  bbForm.base_url = "";
  bbForm.replace_password = false;
}

function openBBEditorForEdit(profile) {
  bbEditorMode.value = "edit";
  bbEditorOpen.value = true;
  bbForm.profile_name = profile.name;
  bbForm.student_id = profile.student_id;
  bbForm.password = "";
  bbForm.base_url = profile.base_url ?? "";
  bbForm.replace_password = false;
}

async function checkBackendHealth() {
  try {
    const response = await getHealth();
    backendStatus.healthy = true;
    backendStatus.message = response.status || "服务响应正常";
  } catch (error) {
    backendStatus.healthy = false;
    backendStatus.message = error.message;
  }
}

async function refreshBlackboard() {
  saving.value = true;
  try {
    const response = await getBlackboardSettings();
    applyBBState(response.data);
    showMessage("Blackboard 配置已加载。");
  } catch (error) {
    showMessage(`加载 Blackboard 配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveBlackboard() {
  saving.value = true;
  try {
    const response = await updateBlackboardSettings({
      student_id: bbForm.student_id,
      password: bbForm.password || null,
      base_url: bbForm.base_url || null,
      replace_password: bbForm.replace_password
    });
    applyBBState(response.data);
    closeBBEditor();
    showMessage("Blackboard 配置已保存。密码仅存储在服务器内存中。");
  } catch (error) {
    showMessage(`保存失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testBlackboard() {
  saving.value = true;
  try {
    const response = await testBlackboardSettings({
      student_id: bbForm.student_id,
      password: bbForm.password || null,
      base_url: bbForm.base_url || null,
      replace_password: bbForm.replace_password
    });
    if (response.success) {
      showMessage("Blackboard 连接测试成功。");
    } else {
      showMessage(`连接测试失败: ${response.data?.error || "未知错误"}`, "error");
    }
  } catch (error) {
    showMessage(`测试失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

function applyProfile(profile) {
  form.profile_name = profile.name;
  form.provider = profile.provider;
  form.model = profile.model;
  form.base_url = profile.base_url ?? "";
  showMessage(`已加载配置 "${profile.name}"。如未设置密钥，请为此运行时设置 API 密钥。`);
}

async function useProfile(profile) {
  saving.value = true;
  try {
    applyProfile(profile);
    const response = await applyLLMProfile(profile.name);
    applyState(response.data);
    closeLLMEditor();
    showMessage(`配置 "${profile.name}" 已应用到运行时。`);
  } catch (error) {
    showMessage(`应用失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshProfiles() {
  const response = await getLLMProfiles();
  profiles.value = response.data ?? [];
}

async function refresh() {
  saving.value = true;
  try {
    const [settingsResponse] = await Promise.all([getLLMSettings(), refreshProfiles()]);
    applyState(settingsResponse.data);
    showMessage("已从后端加载运行时 LLM 配置。");
  } catch (error) {
    showMessage(`加载运行时配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveProfile() {
  if (!form.profile_name.trim()) {
    showMessage("请输入配置名称后再保存。", "error");
    return;
  }

  saving.value = true;
  try {
    await saveLLMProfile({
      name: form.profile_name.trim(),
      provider: form.provider,
      model: form.model,
      base_url: form.base_url || null,
      api_key: form.api_key || null,
      enable_reasoning: form.enable_reasoning
    });
    await refreshProfiles();
    closeLLMEditor();
    showMessage(`配置 "${form.profile_name.trim()}" 已保存。${form.api_key ? "API 密钥已加密保存。" : "API 密钥未更改。"}`);
  } catch (error) {
    showMessage(`保存配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function removeProfile(name) {
  saving.value = true;
  try {
    await deleteLLMProfile(name);
    await refreshProfiles();
    showMessage(`配置 "${name}" 已删除。`);
    if (form.profile_name === name) {
      form.profile_name = "";
    }
  } catch (error) {
    showMessage(`删除失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshBBProfiles() {
  const response = await getBBProfiles();
  bbProfiles.value = response.data ?? [];
}

async function useBBProfile(profile) {
  saving.value = true;
  try {
    bbForm.profile_name = profile.name;
    bbForm.student_id = profile.student_id;
    bbForm.base_url = profile.base_url ?? "";
    bbForm.password = "";
    const response = await applyBBProfile(profile.name);
    applyBBState(response.data);
    closeBBEditor();
    showMessage(`配置 "${profile.name}" 已应用到运行时。`);
  } catch (error) {
    showMessage(`应用失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveBBProfile() {
  if (!bbForm.profile_name.trim()) {
    showMessage("请输入配置名称后再保存。", "error");
    return;
  }

  saving.value = true;
  try {
    await saveBBProfileAPI({
      name: bbForm.profile_name.trim(),
      student_id: bbForm.student_id,
      base_url: bbForm.base_url || null,
      password: bbForm.password || null
    });
    await refreshBBProfiles();
    closeBBEditor();
    showMessage(`Blackboard 配置 "${bbForm.profile_name.trim()}" 已保存。${bbForm.password ? "密码已加密保存。" : "密码未更改。"}`);
  } catch (error) {
    showMessage(`保存配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function removeBBProfile(name) {
  saving.value = true;
  try {
    await deleteBBProfile(name);
    await refreshBBProfiles();
    showMessage(`配置 "${name}" 已删除。`);
    if (bbForm.profile_name === name) {
      bbForm.profile_name = "";
    }
  } catch (error) {
    showMessage(`删除失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function applyEmailState(payload) {
  emailState.smtp_host = payload.smtp_host ?? "smtp.exmail.qq.com";
  emailState.smtp_port = payload.smtp_port ?? 465;
  emailState.smtp_user = payload.smtp_user ?? "";
  emailState.smtp_encryption = payload.smtp_encryption ?? "ssl";
  emailState.imap_host = payload.imap_host ?? "imap.exmail.qq.com";
  emailState.imap_port = payload.imap_port ?? 993;
  emailState.password_configured = Boolean(payload.password_configured);
  emailForm.smtp_host = payload.smtp_host ?? "smtp.exmail.qq.com";
  emailForm.smtp_port = payload.smtp_port ?? 465;
  emailForm.smtp_user = payload.smtp_user ?? "";
  emailForm.smtp_encryption = payload.smtp_encryption ?? "ssl";
  emailForm.imap_host = payload.imap_host ?? "imap.exmail.qq.com";
  emailForm.imap_port = payload.imap_port ?? 993;
  emailForm.password = "";
  emailForm.replace_password = false;
}

function closeEmailEditor() {
  emailEditorOpen.value = false;
}

function openEmailEditorForCreate() {
  emailEditorMode.value = "create";
  emailEditorOpen.value = true;
  emailForm.profile_name = "";
  emailForm.smtp_host = "smtp.exmail.qq.com";
  emailForm.smtp_port = 465;
  emailForm.smtp_user = "";
  emailForm.smtp_encryption = "ssl";
  emailForm.imap_host = "imap.exmail.qq.com";
  emailForm.imap_port = 993;
  emailForm.password = "";
  emailForm.replace_password = false;
}

function openEmailEditorForEdit(profile) {
  emailEditorMode.value = "edit";
  emailEditorOpen.value = true;
  emailForm.profile_name = profile.name;
  emailForm.smtp_host = profile.smtp_host;
  emailForm.smtp_port = profile.smtp_port;
  emailForm.smtp_user = profile.smtp_user;
  emailForm.smtp_encryption = profile.smtp_encryption;
  emailForm.imap_host = profile.imap_host;
  emailForm.imap_port = profile.imap_port;
  emailForm.password = "";
  emailForm.replace_password = false;
}

async function refreshEmail() {
  saving.value = true;
  try {
    const response = await getEmailSettings();
    applyEmailState(response.data);
    showMessage("Email 配置已加载。");
  } catch (error) {
    showMessage(`加载 Email 配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshEmailProfiles() {
  const response = await getEmailProfiles();
  emailProfiles.value = response.data ?? [];
}

async function refreshSearch() {
  saving.value = true;
  try {
    const response = await getSearchSettings();
    applySearchState(response.data);
    showMessage("搜索配置已加载。");
  } catch (error) {
    showMessage(`加载搜索配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveSearch() {
  saving.value = true;
  try {
    const response = await updateSearchSettings({
      provider: searchForm.provider,
      api_key: searchForm.api_key || null,
      replace_api_key: searchForm.replace_api_key,
      timeout: searchForm.timeout
    });
    applySearchState(response.data);
    showMessage("搜索配置已应用到运行时。");
  } catch (error) {
    showMessage(`保存搜索配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testSearch() {
  saving.value = true;
  try {
    const response = await testSearchSettings({
      provider: searchForm.provider,
      api_key: searchForm.api_key || null,
      replace_api_key: searchForm.replace_api_key,
      timeout: searchForm.timeout
    });
    const result = response.data ?? {};
    if (response.success) {
      showMessage(`搜索连接正常。预览: ${result.preview || result.message}`);
    } else {
      showMessage(`搜索测试无结果: ${result.message || "未知错误"}`, "error");
    }
  } catch (error) {
    showMessage(`搜索测试失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

function applyMCPState(payload) {
  mcpServers.value = (payload.servers ?? []).map((server) => ({ ...server }));
}

function objectToPairs(value = {}) {
  return Object.entries(value ?? {}).map(([key, pairValue]) => ({
    key,
    value: String(pairValue ?? "")
  }));
}

function pairsToObject(pairs) {
  return pairs.reduce((acc, pair) => {
    const key = pair.key.trim();
    if (!key && !pair.value.trim()) {
      return acc;
    }
    if (!key) {
      throw new Error("额外字段存在空字段名。");
    }
    acc[key] = pair.value;
    return acc;
  }, {});
}

function mcpPayloadFromForm() {
  const extra = pairsToObject(mcpForm.pairs);
  const base = {
    id: mcpForm.id.trim(),
    enabled: mcpForm.enabled,
    transport: mcpForm.transport,
    tool_prefix: mcpForm.tool_prefix.trim() || null,
    command: mcpForm.command.trim() || null,
    args: mcpForm.argsText.split("\n").map((item) => item.trim()).filter(Boolean),
    env: mcpForm.transport === "stdio" ? extra : {},
    cwd: null,
    url: mcpForm.url.trim() || null,
    headers: mcpForm.transport === "stdio" ? {} : extra,
    timeout: 5,
    read_timeout: 300
  };
  if (!base.id) {
    throw new Error("请输入 Server ID。");
  }
  if (base.transport === "stdio" && !base.command) {
    throw new Error("stdio server 需要 Command。");
  }
  if (base.transport !== "stdio" && !base.url) {
    throw new Error("HTTP/SSE server 需要 URL。");
  }
  return base;
}

function openMCPCreate() {
  mcpEditorMode.value = "create";
  mcpEditorOpen.value = true;
  Object.assign(mcpForm, {
    id: "",
    enabled: true,
    transport: "stdio",
    tool_prefix: "",
    command: "",
    argsText: "",
    url: "",
    pairs: []
  });
}

function editMCPServer(server) {
  mcpEditorMode.value = "edit";
  mcpEditorOpen.value = true;
  Object.assign(mcpForm, {
    id: server.id,
    enabled: Boolean(server.enabled),
    transport: server.transport,
    tool_prefix: server.tool_prefix ?? "",
    command: server.command ?? "",
    argsText: (server.args ?? []).join("\n"),
    url: server.url ?? "",
    pairs: objectToPairs(server.transport === "stdio" ? server.env ?? {} : server.headers ?? {})
  });
}

function addMCPPair() {
  mcpForm.pairs.push({ key: "", value: "" });
}

function removeMCPPair(index) {
  mcpForm.pairs.splice(index, 1);
}

async function persistMCPServers(successMessage) {
  const response = await updateMCPSettings({ servers: mcpServers.value });
  applyMCPState(response.data ?? {});
  showMessage(successMessage || "MCP 配置已应用到运行时。");
}

async function upsertMCPServer() {
  saving.value = true;
  try {
    const payload = mcpPayloadFromForm();
    const index = mcpServers.value.findIndex((server) => server.id === payload.id);
    if (index >= 0) {
      mcpServers.value.splice(index, 1, payload);
    } else {
      mcpServers.value.push(payload);
    }
    mcpEditorOpen.value = false;
    await persistMCPServers(`MCP Server "${payload.id}" 已保存并应用。`);
  } catch (error) {
    showMessage(`MCP 配置无效: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function removeMCPServer(id) {
  saving.value = true;
  try {
    mcpServers.value = mcpServers.value.filter((server) => server.id !== id);
    await persistMCPServers(`MCP Server "${id}" 已删除并应用。`);
  } catch (error) {
    showMessage(`删除 MCP Server 失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshSkills() {
  saving.value = true;
  try {
    const response = await refreshSkillSettings();
    skillList.value = response.data?.skills ?? [];
    showMessage("Skills 已刷新。");
  } catch (error) {
    showMessage(`刷新 Skills 失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshMCP() {
  saving.value = true;
  try {
    const response = await getMCPSettings();
    applyMCPState(response.data ?? {});
    showMessage("MCP 配置已加载。");
  } catch (error) {
    showMessage(`加载 MCP 配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveMCPConfig() {
  saving.value = true;
  try {
    await persistMCPServers("MCP 配置已重新应用到运行时。");
  } catch (error) {
    showMessage(`保存 MCP 配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testMCPServer(server) {
  saving.value = true;
  try {
    const response = await testMCPSettings({ server });
    const result = response.data ?? {};
    if (response.success && result.ok) {
      showMessage(`MCP 连接正常，发现 ${result.tool_count} 个工具。`);
    } else {
      showMessage(`MCP 测试失败: ${result.error || "未知错误"}`, "error");
    }
  } catch (error) {
    showMessage(`MCP 测试失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testMCPForm() {
  try {
    await testMCPServer(mcpPayloadFromForm());
  } catch (error) {
    showMessage(`MCP 配置无效: ${error.message}`, "error");
  }
}

async function saveEmail() {
  saving.value = true;
  try {
    const response = await updateEmailSettings({
      smtp_host: emailForm.smtp_host,
      smtp_port: emailForm.smtp_port,
      smtp_user: emailForm.smtp_user,
      smtp_encryption: emailForm.smtp_encryption,
      imap_host: emailForm.imap_host,
      imap_port: emailForm.imap_port,
      password: emailForm.password || null,
      replace_password: emailForm.replace_password
    });
    applyEmailState(response.data);
    closeEmailEditor();
    showMessage("Email 配置已保存。密码仅存储在服务器内存中。");
  } catch (error) {
    showMessage(`保存失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testEmail() {
  saving.value = true;
  try {
    const response = await testEmailSettings({
      smtp_host: emailForm.smtp_host,
      smtp_port: emailForm.smtp_port,
      smtp_user: emailForm.smtp_user,
      smtp_encryption: emailForm.smtp_encryption,
      imap_host: emailForm.imap_host,
      imap_port: emailForm.imap_port,
      password: emailForm.password || null,
      replace_password: emailForm.replace_password
    });
    if (response.success) {
      showMessage("Email SMTP 连接测试成功。");
    } else {
      showMessage(`连接测试失败: ${response.data?.error || "未知错误"}`, "error");
    }
  } catch (error) {
    showMessage(`测试失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function saveEmailProfileToDb() {
  if (!emailForm.profile_name.trim()) {
    showMessage("请输入配置名称后再保存。", "error");
    return;
  }

  saving.value = true;
  try {
    await saveEmailProfile({
      name: emailForm.profile_name.trim(),
      smtp_host: emailForm.smtp_host,
      smtp_port: emailForm.smtp_port,
      smtp_user: emailForm.smtp_user,
      smtp_encryption: emailForm.smtp_encryption,
      imap_host: emailForm.imap_host,
      imap_port: emailForm.imap_port,
      password: emailForm.password || null
    });
    await refreshEmailProfiles();
    closeEmailEditor();
    showMessage(`Email 配置 "${emailForm.profile_name.trim()}" 已保存。${emailForm.password ? "密码已加密保存。" : "密码未更改。"}`);
  } catch (error) {
    showMessage(`保存配置失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function useEmailProfile(profile) {
  saving.value = true;
  try {
    emailForm.profile_name = profile.name;
    emailForm.smtp_host = profile.smtp_host;
    emailForm.smtp_port = profile.smtp_port;
    emailForm.smtp_user = profile.smtp_user;
    emailForm.smtp_encryption = profile.smtp_encryption;
    emailForm.imap_host = profile.imap_host;
    emailForm.imap_port = profile.imap_port;
    emailForm.password = "";
    const response = await applyEmailProfile(profile.name);
    applyEmailState(response.data);
    closeEmailEditor();
    showMessage(`配置 "${profile.name}" 已应用到运行时。`);
  } catch (error) {
    showMessage(`应用失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function removeEmailProfile(name) {
  saving.value = true;
  try {
    await deleteEmailProfile(name);
    await refreshEmailProfiles();
    showMessage(`配置 "${name}" 已删除。`);
    if (emailForm.profile_name === name) {
      emailForm.profile_name = "";
    }
  } catch (error) {
    showMessage(`删除失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function save() {
  saving.value = true;
  try {
    const response = await updateLLMSettings({
      provider: form.provider,
      model: form.model,
      base_url: form.base_url || null,
      api_key: form.api_key || null,
      enable_reasoning: form.enable_reasoning
    });
    applyState(response.data);
    closeLLMEditor();
    showMessage("运行时配置已保存。API 密钥仅保留在服务器端。");
  } catch (error) {
    showMessage(`保存失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function testConnection() {
  saving.value = true;
  try {
    const response = await testLLMSettings({
      provider: form.provider,
      model: form.model,
      base_url: form.base_url || null,
      api_key: form.api_key || null,
      enable_reasoning: form.enable_reasoning
    });
    const result = response.data;
    showMessage(`连接正常，耗时 ${result.latency_ms}ms。预览: ${result.preview}`);
  } catch (error) {
    showMessage(`连接测试失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

async function refreshAll() {
  saving.value = true;
  try {
    const [
      llmResponse,
      bbResponse,
      emailResponse,
      searchResponse,
      skillsResponse,
      mcpResponse,
      llmProfilesResponse,
      bbProfilesResponse,
      emailProfilesResponse,
      healthResponse
    ] = await Promise.all([
      getLLMSettings(),
      getBlackboardSettings(),
      getEmailSettings(),
      getSearchSettings(),
      refreshSkillSettings(),
      getMCPSettings(),
      getLLMProfiles(),
      getBBProfiles(),
      getEmailProfiles(),
      getHealth()
    ]);

    applyState(llmResponse.data);
    applyBBState(bbResponse.data);
    applyEmailState(emailResponse.data);
    applySearchState(searchResponse.data);
    skillList.value = skillsResponse.data?.skills ?? [];
    applyMCPState(mcpResponse.data ?? {});
    profiles.value = llmProfilesResponse.data ?? [];
    bbProfiles.value = bbProfilesResponse.data ?? [];
    emailProfiles.value = emailProfilesResponse.data ?? [];
    backendStatus.healthy = true;
    backendStatus.message = healthResponse.status || "服务响应正常";
    showMessage("所有配置与后端状态已刷新。");
  } catch (error) {
    backendStatus.healthy = false;
    backendStatus.message = error.message;
    showMessage(`刷新失败: ${error.message}`, "error");
  } finally {
    saving.value = false;
  }
}

watch(activeSection, () => {
  clearMessage();
});

onMounted(async () => {
  await Promise.all([
    refresh(),
    refreshBlackboard(),
    refreshBBProfiles(),
    refreshEmail(),
    refreshEmailProfiles(),
    refreshSearch(),
    refreshSkills(),
    refreshMCP(),
    checkBackendHealth()
  ]);
});

onBeforeUnmount(() => {
  clearMessage();
});
</script>

<style scoped>
.settings-panel {
  position: relative;
  max-width: 1120px;
  margin: 0 auto;
  padding: 28px;
  border-radius: 24px;
  background:
    radial-gradient(circle at top left, rgba(249, 115, 22, 0.12), transparent 24%),
    radial-gradient(circle at bottom right, rgba(31, 111, 120, 0.12), transparent 28%),
    rgba(255, 255, 255, 0.94);
  box-shadow: 0 24px 60px rgba(28, 36, 48, 0.14);
  backdrop-filter: blur(20px);
  max-height: 84vh;
  overflow: hidden;
}

.settings-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  margin-bottom: 22px;
}

.header-title h2 {
  margin: 0;
  font-family: var(--font-heading);
  font-size: 28px;
  color: var(--text-primary);
}

.header-copy {
  margin: 10px 0 0;
  max-width: 560px;
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1.6;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.settings-layout {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 20px;
  min-height: 0;
}

.settings-nav {
  display: grid;
  align-content: start;
  gap: 10px;
  padding: 16px;
  border-radius: 22px;
  background: rgba(17, 24, 39, 0.04);
  border: 1px solid rgba(148, 163, 184, 0.2);
  transition: width 0.2s ease, padding 0.2s ease;
}

.settings-nav.collapsed {
  width: 84px;
  padding: 16px 10px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px;
  border: 1px solid transparent;
  border-radius: 18px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-item:hover {
  background: rgba(249, 115, 22, 0.08);
}

.nav-item.active {
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.16), rgba(31, 111, 120, 0.14));
  border-color: rgba(249, 115, 22, 0.18);
}

.nav-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 14px;
  background: white;
  color: var(--text-primary);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  flex-shrink: 0;
}

.nav-copy {
  display: grid;
  gap: 4px;
}

.nav-copy strong {
  font-size: 14px;
  color: var(--text-primary);
}

.nav-copy small {
  font-size: 12px;
  color: var(--text-muted);
}

.settings-content {
  display: grid;
  gap: 16px;
  max-height: calc(84vh - 110px);
  overflow-y: auto;
  padding-right: 6px;
  padding-bottom: 10px;
}

.content-panel {
  padding: 22px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: 0 12px 30px rgba(28, 36, 48, 0.06);
}

.hero-panel {
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.1), rgba(255, 255, 255, 0.95) 40%, rgba(31, 111, 120, 0.08));
}

.bb-hero {
  background: linear-gradient(135deg, rgba(31, 111, 120, 0.12), rgba(255, 255, 255, 0.95) 38%, rgba(249, 115, 22, 0.08));
}

.backend-hero {
  background: linear-gradient(135deg, rgba(14, 116, 144, 0.12), rgba(255, 255, 255, 0.94) 45%, rgba(15, 23, 42, 0.06));
}

.search-hero {
  background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(255, 255, 255, 0.94) 42%, rgba(14, 116, 144, 0.1));
}

.developer-panel {
  background: linear-gradient(135deg, rgba(15, 23, 42, 0.08), rgba(255, 255, 255, 0.94) 40%, rgba(249, 115, 22, 0.1));
}

.panel-heading,
.section-top,
.profiles-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.panel-heading h3 {
  margin: 4px 0 0;
  font-family: var(--font-heading);
  font-size: 22px;
  color: var(--text-primary);
}

.eyebrow {
  margin: 0 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 11px;
  font-weight: 700;
  color: var(--accent-orange);
}

.badge {
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.12);
  color: #dc2626;
  font-size: 12px;
  font-weight: 700;
}

.badge.ready {
  background: rgba(34, 197, 94, 0.12);
  color: #15803d;
}

.hint {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0;
  line-height: 1.6;
}

.compact {
  margin-top: 6px;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 18px;
}

.backend-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.status-card {
  display: grid;
  gap: 6px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.status-card.wide {
  grid-column: 1 / -1;
}

.status-card span {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.status-card strong {
  font-size: 15px;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-word;
}

.status-card small {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.5;
}

.profile-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.profile-item,
.dev-card {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  padding: 16px;
  border-radius: 18px;
  background: white;
  border: 1px solid var(--border-light);
}

.profile-info strong,
.dev-card strong,
.section-top strong {
  font-size: 15px;
  color: var(--text-primary);
}

.profile-info p,
.dev-card p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.profile-info small {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
}

.profile-actions,
.dev-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
}

.mcp-server-card {
  align-items: stretch;
  background: linear-gradient(180deg, #ffffff, rgba(248, 250, 252, 0.92));
}

.mcp-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.transport-pill {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 4px 9px;
  border-radius: 999px;
  background: rgba(31, 111, 120, 0.1);
  color: var(--accent-teal);
  font-size: 11px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.key-value-editor {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.key-value-top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.key-value-rows {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.key-value-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr) auto;
  gap: 10px;
  align-items: center;
}

.icon-btn {
  white-space: nowrap;
}

.action-btn {
  background: rgba(31, 41, 55, 0.06);
  color: var(--text-primary);
}

.action-btn:hover {
  background: rgba(31, 41, 55, 0.12);
}

.config-form {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-top: 18px;
}

.bb-form {
  display: grid;
  gap: 16px;
  margin-top: 18px;
}

.editor-panel {
  border-style: dashed;
  border-color: rgba(218, 106, 30, 0.2);
  background: linear-gradient(180deg, rgba(255, 247, 239, 0.92), rgba(255, 255, 255, 0.94));
}

.panel-actions {
  margin-top: 16px;
}

label {
  display: grid;
  gap: 8px;
}

label span {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

input,
select,
textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid var(--border-light);
  background: white;
  font-size: 14px;
  font-family: inherit;
  transition: all 0.2s ease;
}

input:focus,
select:focus,
textarea:focus {
  outline: none;
  border-color: var(--accent-orange);
  box-shadow: 0 0 0 4px var(--accent-orange-subtle);
}

.full {
  grid-column: 1 / -1;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}

.inline-actions {
  justify-content: flex-start;
  margin-top: 18px;
}

button {
  padding: 10px 16px;
  border: none;
  border-radius: 999px;
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
}

button[type="submit"],
.section-top > button,
.dev-card button {
  background: var(--accent-orange);
  color: white;
}

button[type="submit"]:hover,
.section-top > button:hover,
.dev-card button:hover {
  background: #ea580c;
}

.secondary {
  background: var(--bg-hover);
  color: var(--text-primary);
}

.secondary:hover {
  background: var(--border-subtle);
}

.apply-btn {
  background: var(--accent-orange-subtle);
  color: var(--accent-orange);
}

.apply-btn:hover {
  background: var(--accent-orange);
  color: white;
}

.delete-btn {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.delete-btn:hover {
  background: #dc2626;
  color: white;
}

button:disabled {
  opacity: 0.6;
  cursor: wait;
}

.close-btn,
.collapse-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(28, 36, 48, 0.08);
  color: var(--text-primary);
}

.close-btn:hover,
.collapse-btn:hover {
  background: rgba(28, 36, 48, 0.12);
}

.result {
  position: absolute;
  right: 28px;
  bottom: 28px;
  z-index: 6;
  max-width: min(520px, calc(100% - 56px));
  margin: 0;
  padding: 14px 18px;
  border-radius: 16px;
  background: rgba(34, 197, 94, 0.1);
  color: #15803d;
  font-size: 13px;
  font-weight: 600;
  border: 1px solid rgba(34, 197, 94, 0.14);
  box-shadow: 0 14px 24px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(12px);
  line-height: 1.5;
  word-break: break-word;
}

.result.error {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
  border-color: rgba(239, 68, 68, 0.16);
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity 0.22s ease, transform 0.22s ease;
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@media (max-width: 980px) {
  .settings-panel {
    padding: 20px;
    max-height: 90vh;
  }

  .settings-layout {
    grid-template-columns: 1fr;
  }

  .settings-nav,
  .settings-nav.collapsed {
    width: auto;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    padding: 12px;
  }

  .nav-copy {
    display: grid !important;
  }

  .result {
    right: 20px;
    bottom: 20px;
    max-width: calc(100% - 40px);
  }

  .status-grid,
  .backend-grid,
  .config-form {
    grid-template-columns: 1fr;
  }

  .key-value-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .settings-header,
  .panel-heading,
  .section-top,
  .profile-item,
  .dev-card {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    width: 100%;
    justify-content: flex-start;
  }

  .settings-nav,
  .settings-nav.collapsed {
    grid-template-columns: 1fr;
  }
}
</style>

<style scoped>
.toggle-label {
  display: flex;
  align-items: center;
  cursor: pointer;
}
.toggle-row {
  display: flex;
  justify-content: space-between;
  width: 100%;
}
.toggle-input {
  width: auto;
  margin-left: 10px;
}
</style>
