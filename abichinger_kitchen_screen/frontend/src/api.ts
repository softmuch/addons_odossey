import { useClient } from './odoo'

export async function setKitchenState(
  change_id: number,
  line_ids: number[],
  state: string,
): Promise<void> {
  const { orm } = await useClient()
  await orm.call('ab_pos.order.change.line', 'set_state', [line_ids, state])
}

export async function updatePriority(
  ids: number[],
  model: string = 'ab_pos.order.change',
  priority: number = 0,
): Promise<void> {
  const { orm } = await useClient()
  await orm.call(model, 'update_priority', [ids, priority])
}
