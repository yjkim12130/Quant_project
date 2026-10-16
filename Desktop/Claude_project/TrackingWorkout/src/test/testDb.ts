import { WorkoutDB } from '../db/schema';

let seq = 0;
/** 테스트마다 이름이 다른 DB — 서로 간섭하지 않는다 */
export function makeTestDb(): WorkoutDB {
  seq += 1;
  return new WorkoutDB(`test-${Date.now()}-${seq}`);
}
