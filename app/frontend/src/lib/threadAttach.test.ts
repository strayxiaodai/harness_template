import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import {
  ATTACH_PRESERVED_KEYS,
  applyAttachFields,
  formatThreadSelectLabel,
  shouldDisableThreadPicker,
} from './threadAttach.ts'

describe('threadAttach', () => {
  it('F14 disables picker while streaming', () => {
    assert.equal(shouldDisableThreadPicker('streaming'), true)
    assert.equal(shouldDisableThreadPicker('idle'), false)
    assert.equal(shouldDisableThreadPicker('idle', true), true)
  })

  it('F15 truncates long task labels', () => {
    const label = formatThreadSelectLabel({
      thread_id: 'abcdef12-9999',
      task: 'a'.repeat(50),
    })
    assert.match(label, /^a{36}… \(abcdef12…\)$/)
  })

  it('F13 applyAttachFields sets id/task/planText only', () => {
    const fields = applyAttachFields({
      thread_id: 'tid',
      task: 'Do X',
      slug: '',
      started_at: '',
      plan: ['one', 'two'],
    })
    assert.deepEqual(fields, {
      threadId: 'tid',
      task: 'Do X',
      planText: 'one\ntwo',
    })
    assert.deepEqual([...ATTACH_PRESERVED_KEYS], [
      'timeline',
      'phase',
      'runResponse',
      'selectedStepId',
      'distillResult',
    ])
  })
})
