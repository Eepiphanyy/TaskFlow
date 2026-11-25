import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { register as registerRequest } from '../api/auth.js'

function getFirstBackendError(error) {
  const errors = error?.response?.data?.errors

  if (errors && typeof errors === 'object') {
    for (const value of Object.values(errors)) {
      if (Array.isArray(value) && value.length > 0) {
        return String(value[0])
      }

      if (typeof value === 'string') {
        return value
      }
    }
  }

  return error?.response?.data?.message
    || error?.userMessage
    || error?.message
    || '注册失败，请稍后重试'
}

export function useRegister({
  formRef,
  router = useRouter(),
  registerUser = registerRequest
} = {}) {
  const form = reactive({
    username: '',
    email: '',
    password: '',
    password_confirm: ''
  })
  const loading = ref(false)
  const errorMessage = ref('')

  const rules = {
    username: [
      { required: true, message: '请输入用户名', trigger: 'blur' }
    ],
    email: [
      { required: true, message: '请输入邮箱', trigger: 'blur' },
      {
        type: 'email',
        message: '请输入有效的邮箱地址',
        trigger: ['blur', 'change']
      }
    ],
    password: [
      { required: true, message: '请输入密码', trigger: 'blur' },
      {
        min: 8,
        message: '密码长度不能少于 8 位',
        trigger: 'blur'
      }
    ],
    password_confirm: [
      {
        validator: (_rule, value, callback) => {
          if (!value) {
            callback(new Error('请再次输入密码'))
          } else if (value !== form.password) {
            callback(new Error('两次输入的密码不一致'))
          } else {
            callback()
          }
        },
        trigger: ['blur', 'change']
      }
    ]
  }

  async function handleRegister() {
    if (loading.value) {
      return false
    }

    errorMessage.value = ''

    if (!formRef?.value) {
      return false
    }

    try {
      await formRef.value.validate()
    } catch {
      return false
    }

    loading.value = true

    try {
      await registerUser({
        username: form.username.trim(),
        email: form.email.trim(),
        password: form.password,
        password_confirm: form.password_confirm
      })

      form.password = ''
      form.password_confirm = ''
      await router.replace({
        name: 'login',
        query: {
          registered: '1'
        }
      })
      return true
    } catch (error) {
      errorMessage.value = getFirstBackendError(error)
      return false
    } finally {
      loading.value = false
    }
  }

  return {
    form,
    rules,
    loading,
    errorMessage,
    handleRegister
  }
}
