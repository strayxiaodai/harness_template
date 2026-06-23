import { useCallback, useEffect, useState } from 'react'
import { fetchSkill, fetchSkills } from '../lib/api'
import { formatFetchError } from '../lib/errors'
import type { SkillDetail, SkillSummary } from '../types/api'

export function useSkills() {
  const [skills, setSkills] = useState<SkillSummary[]>([])
  const [selectedSlug, setSelectedSlug] = useState('')
  const [selectedSkill, setSelectedSkill] = useState<SkillDetail | null>(null)
  const [loading, setLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshSkills = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const items = await fetchSkills()
      setSkills(items)
    } catch (err) {
      setError(formatFetchError(err, 'Failed to load skills'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refreshSkills()
  }, [refreshSkills])

  const selectSkill = useCallback(async (slug: string) => {
    setSelectedSlug(slug)
    if (!slug) {
      setSelectedSkill(null)
      return
    }

    setDetailLoading(true)
    setError(null)
    try {
      const detail = await fetchSkill(slug)
      setSelectedSkill(detail)
    } catch (err) {
      setSelectedSkill(null)
      setError(formatFetchError(err, 'Failed to load skill'))
    } finally {
      setDetailLoading(false)
    }
  }, [])

  return {
    skills,
    selectedSlug,
    selectedSkill,
    loading,
    detailLoading,
    error,
    refreshSkills,
    selectSkill,
    setSelectedSlug,
    clearError: () => setError(null),
  }
}
