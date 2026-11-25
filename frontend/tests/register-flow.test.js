import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'

const { useRegister } = await import('../src/composables/useRegister.js')

let calls
let router
let registerUser

function validFormRef() {
  return {
    value: {
      validate: async () => true
    }
  }
}

function createRegistration(overrides = {}) {
  return useRegister({
    formRef: overrides.formRef ?? validFormRef(),
    router,
    registerUser
  })
}

function fillForm(flow, overrides = {}) {
  flow.form.username = overrides.username ?? 'new_user'
  flow.form.email = overrides.email ?? 'new_user@example.com'
  flow.form.password = overrides.password ?? 'TaskFlow#2026'
  flow.form.password_confirm = (
    overrides.password_confirm ?? 'TaskFlow#2026'
  )
}

function backendValidationError(errors) {
  const error = new Error('Registration failed')
  error.response = {
    status: 400,
    data: {
      code: 400,
      message: '注册信息校验失败',
      errors
    }
  }
  return error
}

beforeEach(() => {
  calls = []
  router = {
    replace: async (location) => {
      calls.push(['replace', location])
    }
  }
  registerUser = async (data) => {
    calls.push(['register', data])
    return {
      data: {
        code: 201,
        message: '注册成功',
        data: {
          id: 1,
          username: data.username,
          email: data.email
        }
      }
    }
  }
})

test('successful registration sends fields and redirects to login', async () => {
  const registration = createRegistration()
  fillForm(registration, {
    username: '  new_user  ',
    email: '  new_user@example.com  '
  })

  const result = await registration.handleRegister()

  assert.equal(result, true)
  assert.deepEqual(calls[0], [
    'register',
    {
      username: 'new_user',
      email: 'new_user@example.com',
      password: 'TaskFlow#2026',
      password_confirm: 'TaskFlow#2026'
    }
  ])
  assert.deepEqual(calls[1], [
    'replace',
    {
      name: 'login',
      query: { registered: '1' }
    }
  ])
  assert.equal(registration.loading.value, false)
  assert.equal(registration.form.password, '')
  assert.equal(registration.form.password_confirm, '')
})

test('duplicate username shows the backend error without redirect', async () => {
  registerUser = async () => {
    throw backendValidationError({
      username: ['该用户名已被使用。']
    })
  }
  const registration = createRegistration()
  fillForm(registration)

  const result = await registration.handleRegister()

  assert.equal(result, false)
  assert.equal(registration.errorMessage.value, '该用户名已被使用。')
  assert.equal(calls.some(([name]) => name === 'replace'), false)
})

test('duplicate email shows the backend error', async () => {
  registerUser = async () => {
    throw backendValidationError({
      email: ['该邮箱已被使用。']
    })
  }
  const registration = createRegistration()
  fillForm(registration)

  const result = await registration.handleRegister()

  assert.equal(result, false)
  assert.equal(registration.errorMessage.value, '该邮箱已被使用。')
  assert.equal(calls.some(([name]) => name === 'replace'), false)
})

test('password confirmation rule rejects mismatched passwords', () => {
  const registration = createRegistration()
  fillForm(registration, {
    password_confirm: 'Different#2026'
  })
  const validator = registration.rules.password_confirm[0].validator
  let validationError = null

  validator(
    {},
    registration.form.password_confirm,
    (error) => {
      validationError = error
    }
  )

  assert.equal(validationError.message, '两次输入的密码不一致')
})

test('invalid Element Plus form prevents the API request', async () => {
  const invalidFormRef = {
    value: {
      validate: async () => {
        throw new Error('Validation failed')
      }
    }
  }
  const registration = createRegistration({
    formRef: invalidFormRef
  })
  fillForm(registration)

  assert.equal(await registration.handleRegister(), false)
  assert.equal(calls.length, 0)
  assert.equal(registration.loading.value, false)
})

test('registration failure does not redirect', async () => {
  registerUser = async () => {
    throw new Error('Server unavailable')
  }
  const registration = createRegistration()
  fillForm(registration)

  const result = await registration.handleRegister()

  assert.equal(result, false)
  assert.equal(registration.errorMessage.value, 'Server unavailable')
  assert.equal(calls.some(([name]) => name === 'replace'), false)
})

test('loading prevents duplicate registration submissions', async () => {
  let notifyStarted
  let resolveRegistration
  const started = new Promise((resolve) => {
    notifyStarted = resolve
  })
  let requestCount = 0
  registerUser = (data) => {
    requestCount += 1
    return new Promise((resolve) => {
      resolveRegistration = () => resolve({
        data: {
          code: 201,
          data
        }
      })
      notifyStarted()
    })
  }
  const registration = createRegistration()
  fillForm(registration)

  const firstRequest = registration.handleRegister()
  await started
  assert.equal(await registration.handleRegister(), false)
  assert.equal(requestCount, 1)

  resolveRegistration()
  assert.equal(await firstRequest, true)
  assert.equal(registration.loading.value, false)
})
