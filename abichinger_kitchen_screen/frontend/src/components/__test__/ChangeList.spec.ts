import { describe, it, expect } from 'vitest'

import { mount } from '@vue/test-utils'
import ChangeList from '@/components/ChangeList.vue'
import { generateOrder, mockPosStore } from '@/dev'

describe('ChangeList', () => {
  it('renders properly', async () => {
    const order = generateOrder(mockPosStore(), 'cooking', 1)
    const changes = order.changes

    const wrapper = mount(ChangeList, {
      props: {
        changes: changes,
      },
    })

    expect(wrapper.text()).toContain(order.trackingNumber)
    expect(wrapper.text()).toContain(changes[0].lines[0].product.display_name)
  })
})
