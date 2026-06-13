<template>
  <section>
    <PageHeader eyebrow="记录" title="探视记录" description="登记签到、签退、体温、接待员工和探视摘要。" />

    <article class="panel">
      <h3>新增探视记录</h3>
      <VisitRecordForm :model="form" :appointments="appointments" @submit="saveVisit" />
      <p v-if="message" class="message">{{ message }}</p>
    </article>

    <article class="panel">
      <h3>导出与汇总</h3>
      <div class="filter-bar">
        <label>
          开始日期
          <input type="date" v-model="filters.start_date" />
        </label>
        <label>
          结束日期
          <input type="date" v-model="filters.end_date" />
        </label>
        <button type="button" class="primary" style="background:#6b7280;" @click="loadSummary">查询汇总</button>
        <a :href="visitsApi.exportUrl(filters)" class="primary">导出 CSV</a>
      </div>
      <EmptyState v-if="summary.length === 0" />
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>老人姓名</th>
              <th>房间号</th>
              <th>探视日期</th>
              <th>接待员工</th>
              <th>探视次数</th>
              <th>访客总人数</th>
              <th>来访家属</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in summary" :key="idx">
              <td>{{ row.resident_name }}</td>
              <td>{{ row.room_number }}</td>
              <td>{{ row.visit_date }}</td>
              <td>{{ row.staff_name }}</td>
              <td>{{ row.visit_count }}</td>
              <td>{{ row.total_visitors }}</td>
              <td>{{ row.families.join('、') }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article class="panel">
      <h3>记录列表</h3>
      <EmptyState v-if="visits.length === 0" />
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>老人</th>
              <th>家属</th>
              <th>签到</th>
              <th>签退</th>
              <th>体温</th>
              <th>接待员工</th>
              <th>摘要</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in visits" :key="item.id">
              <td>{{ item.appointment.resident.name }}</td>
              <td>{{ item.appointment.family_name }}</td>
              <td>{{ formatTime(item.check_in_time) }}</td>
              <td>{{ item.check_out_time ? formatTime(item.check_out_time) : '未签退' }}</td>
              <td>{{ item.visitor_temperature || '未登记' }}</td>
              <td>{{ item.staff_name }}</td>
              <td>{{ item.summary || '无' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import EmptyState from '../components/EmptyState.vue'
import PageHeader from '../components/PageHeader.vue'
import VisitRecordForm from '../components/VisitRecordForm.vue'
import { appointmentsApi } from '../services/appointments'
import { visitsApi } from '../services/visits'

const visits = ref([])
const summary = ref([])
const appointments = ref([])
const message = ref('')
const filters = reactive({
  start_date: '',
  end_date: ''
})
const initialForm = {
  appointment_id: '',
  check_in_time: '',
  check_out_time: '',
  visitor_temperature: '',
  staff_name: '',
  summary: ''
}
const form = reactive({ ...initialForm })

onMounted(async () => {
  await Promise.all([loadAppointments(), loadVisits(), loadSummary()])
})

async function loadAppointments() {
  appointments.value = (await appointmentsApi.list()).results
}

async function loadVisits() {
  visits.value = (await visitsApi.list()).results
}

async function loadSummary() {
  summary.value = (await visitsApi.summary(filters)).results
}

async function saveVisit() {
  await visitsApi.create(form)
  Object.assign(form, initialForm)
  message.value = '探视记录已登记'
  await Promise.all([loadAppointments(), loadVisits(), loadSummary()])
}

function formatTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN') : ''
}
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.filter-bar label {
  display: grid;
  gap: 6px;
  font-size: 14px;
  width: auto;
}

.filter-bar input[type="date"] {
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 14px;
  width: auto;
  min-width: 160px;
}

.filter-bar a.primary {
  text-decoration: none;
  display: inline-block;
  text-align: center;
}
</style>
