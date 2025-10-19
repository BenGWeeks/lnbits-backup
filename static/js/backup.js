/* globals Quasar, Vue, _, windowMixin, LNbits, LOCALE */

window.app = Vue.createApp({
  el: '#vue',
  mixins: [window.windowMixin],
  data() {
    return {
      userLocale: navigator.language || 'en-GB',
      schedules: [],
      scheduleTable: {
        columns: [
          {name: 'name', align: 'left', label: 'Name', field: 'name', sortable: true},
          {name: 'backup_path', align: 'left', label: 'Backup Path', field: 'backup_path', sortable: true},
          {name: 'frequency_type', align: 'center', label: 'Frequency', field: 'frequency_type', sortable: true},
          {name: 'next_backup_date', align: 'left', label: 'Next Backup', field: 'next_backup_date', sortable: true},
          {name: 'status', align: 'center', label: 'Status', field: 'active', sortable: true}
        ],
        pagination: {
          rowsPerPage: 10
        },
        filter: '',
        loading: false
      },
      formDialog: {
        show: false,
        loading: false,
        data: {}
      },
      frequencyOptions: [
        {label: 'Hourly', value: 'hourly'},
        {label: 'Daily', value: 'daily'},
        {label: 'Weekly', value: 'weekly'},
        {label: 'Monthly', value: 'monthly'}
      ]
    }
  },
  methods: {
    getSchedules() {
      console.log('🔍 Loading backup schedules...')
      this.scheduleTable.loading = true

      const wallet = this.g.user.wallets[0]
      if (!wallet) {
        console.error('❌ No wallet found for authentication')
        this.scheduleTable.loading = false
        return
      }

      LNbits.api
        .request(
          'GET',
          '/backup/api/v1/schedules',
          wallet.adminkey
        )
        .then(response => {
          console.log('✅ Schedules loaded:', response.data)
          this.schedules = response.data.map(schedule => ({
            ...schedule,
            backing_up: false  // Add loading state for manual backups
          }))
        })
        .catch(err => {
          console.error('❌ Error loading schedules:', err)
          LNbits.utils.notifyApiError(err)
        })
        .finally(() => {
          this.scheduleTable.loading = false
        })
    },
    refreshSchedules() {
      this.getSchedules()
    },
    closeFormDialog() {
      this.formDialog.show = false
      this.formDialog.data = {}
    },
    openCreateDialog() {
      // Default to 5 minutes in the future
      const fiveMinutesFromNow = new Date(Date.now() + 5 * 60 * 1000)
      const defaultStart = this.toQuasarDatetimeString(fiveMinutesFromNow)

      this.formDialog.data = {
        wallet: this.g.user.wallets[0].id,
        frequency_type: 'daily',
        active: true,
        compress: true,
        retention_count: 7,
        backup_path: './backups',
        start_datetime: defaultStart,
        next_backup_date: defaultStart
      }
      this.formDialog.show = true
      console.log('📅 Form opened with default start datetime:', defaultStart)
    },
    openEditDialog(schedule) {
      // Convert timestamps to datetime-local format
      const start = schedule.start_datetime ? this.toQuasarDatetimeString(new Date(schedule.start_datetime * 1000)) : ''
      const end = schedule.end_datetime ? this.toQuasarDatetimeString(new Date(schedule.end_datetime * 1000)) : ''
      const next = schedule.next_backup_date ? this.toQuasarDatetimeString(new Date(schedule.next_backup_date * 1000)) : ''

      this.formDialog.data = {
        id: schedule.id,
        name: schedule.name,
        wallet: schedule.wallet,
        backup_path: schedule.backup_path,
        frequency_type: schedule.frequency_type,
        start_datetime: start,
        end_datetime: end,
        next_backup_date: next,
        retention_count: schedule.retention_count || 7,
        compress: schedule.compress !== false,
        active: schedule.active
      }
      this.formDialog.show = true
    },
    saveSchedule(event) {
      if (event) {
        event.preventDefault()
      }

      if (!this.formDialog.show) {
        return
      }

      // Validate required fields
      const errors = []
      if (!this.formDialog.data.name) errors.push('Schedule name is required')
      if (!this.formDialog.data.backup_path) errors.push('Backup path is required')
      if (!this.formDialog.data.frequency_type) errors.push('Frequency is required')
      if (!this.formDialog.data.start_datetime) errors.push('Start date & time is required')
      if (!this.formDialog.data.retention_count || this.formDialog.data.retention_count < 1) {
        errors.push('Retention count must be at least 1')
      }

      if (errors.length > 0) {
        Quasar.Notify.create({
          type: 'negative',
          message: errors.join('<br>'),
          html: true,
          timeout: 5000
        })
        return
      }

      // Validate start datetime is in the future (only for new schedules)
      if (!this.formDialog.data.id && this.formDialog.data.start_datetime) {
        const startDate = new Date(this.formDialog.data.start_datetime)
        const now = new Date()
        const oneMinuteFromNow = new Date(now.getTime() + 60 * 1000)
        if (startDate < oneMinuteFromNow) {
          Quasar.Notify.create({
            type: 'negative',
            message: 'Start date & time must be at least 1 minute in the future',
            timeout: 5000
          })
          return
        }
      }

      this.formDialog.loading = true

      const wallet = this.g.user.wallets[0]
      const isEdit = !!this.formDialog.data.id

      const method = isEdit ? 'PUT' : 'POST'
      const url = isEdit
        ? `/backup/api/v1/schedules/${this.formDialog.data.id}`
        : '/backup/api/v1/schedules'

      // Prepare data payload
      const payload = {
        ...this.formDialog.data,
        // Ensure next_backup_date is set
        next_backup_date: this.formDialog.data.next_backup_date || this.formDialog.data.start_datetime
      }

      console.log(`${isEdit ? '✏️' : '➕'} Saving schedule:`, payload)

      LNbits.api
        .request(method, url, wallet.adminkey, payload)
        .then(response => {
          console.log('✅ Schedule saved:', response.data)
          Quasar.Notify.create({
            type: 'positive',
            message: `Backup schedule ${isEdit ? 'updated' : 'created'} successfully`,
            timeout: 3000
          })
          this.closeFormDialog()
          this.getSchedules()
        })
        .catch(err => {
          console.error('❌ Error saving schedule:', err)
          LNbits.utils.notifyApiError(err)
        })
        .finally(() => {
          this.formDialog.loading = false
        })
    },
    deleteSchedule(schedule) {
      Quasar.Dialog.create({
        title: 'Delete Backup Schedule',
        message: `Are you sure you want to delete "${schedule.name}"? This will also delete all backup history for this schedule.`,
        ok: {
          label: 'Delete',
          color: 'negative'
        },
        cancel: {
          label: 'Cancel',
          flat: true
        }
      }).onOk(() => {
        const wallet = this.g.user.wallets[0]

        LNbits.api
          .request(
            'DELETE',
            `/backup/api/v1/schedules/${schedule.id}`,
            wallet.adminkey
          )
          .then(() => {
            console.log('✅ Schedule deleted:', schedule.name)
            Quasar.Notify.create({
              type: 'positive',
              message: 'Backup schedule deleted successfully',
              timeout: 3000
            })
            this.getSchedules()
          })
          .catch(err => {
            console.error('❌ Error deleting schedule:', err)
            LNbits.utils.notifyApiError(err)
          })
      })
    },
    manualBackup(schedule) {
      console.log('🚀 Triggering manual backup for:', schedule.name)

      // Set loading state
      schedule.backing_up = true

      const wallet = this.g.user.wallets[0]

      LNbits.api
        .request(
          'POST',
          `/backup/api/v1/backup/manual?schedule_id=${schedule.id}`,
          wallet.adminkey
        )
        .then(response => {
          console.log('✅ Manual backup completed:', response.data)
          Quasar.Notify.create({
            type: 'positive',
            message: `Backup completed successfully<br><small>${response.data.file_path}</small>`,
            html: true,
            timeout: 5000
          })
          this.getSchedules()  // Refresh to show updated last_success_time
        })
        .catch(err => {
          console.error('❌ Error executing manual backup:', err)
          LNbits.utils.notifyApiError(err)
        })
        .finally(() => {
          schedule.backing_up = false
        })
    },
    formatFrequency(freq) {
      const map = {
        'hourly': 'Hourly',
        'daily': 'Daily',
        'weekly': 'Weekly',
        'monthly': 'Monthly'
      }
      return map[freq] || freq
    },
    formatDatetime(timestamp) {
      if (!timestamp) return '-'
      const date = new Date(timestamp * 1000)
      return date.toLocaleString(this.userLocale, {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      })
    },
    formatFileSize(bytes) {
      if (!bytes) return '-'
      const mb = bytes / 1024 / 1024
      if (mb >= 1) {
        return `${mb.toFixed(2)} MB`
      }
      const kb = bytes / 1024
      return `${kb.toFixed(2)} KB`
    },
    toQuasarDatetimeString(date) {
      // Convert Date object to "YYYY-MM-DDTHH:mm" format for datetime-local input
      const year = date.getFullYear()
      const month = String(date.getMonth() + 1).padStart(2, '0')
      const day = String(date.getDate()).padStart(2, '0')
      const hours = String(date.getHours()).padStart(2, '0')
      const minutes = String(date.getMinutes()).padStart(2, '0')
      return `${year}-${month}-${day}T${hours}:${minutes}`
    }
  },
  created() {
    // Load schedules on mount
    this.getSchedules()
  }
})

window.app.use(Quasar).mount('#vue')
