import db from "../db/db.js";
import { buildWorkingBlocks, subtractBusy } from "./availability.utils.js";

export async function getUserAvailability(userId, start, end) {
  const startDate = new Date(start);
  const endDate = new Date(end);

  const prefs = await db.query(`
    SELECT day_of_week, start_time, end_time
    FROM time_slot_preferences
    WHERE user_id = $1
  `, [userId]);

  const busy = await db.query(`
    SELECT 
      (m.start_time - make_interval(mins => m.setup_minutes)) AS start,
      (m.end_time + make_interval(mins => m.cleanup_minutes)) AS end
    FROM meetings m
    JOIN meeting_attendees ma ON ma.meeting_id = m.id
    WHERE ma.user_id = $1
    AND ma.status = 'accepted'
    AND m.start_time < $3
    AND m.end_time > $2
    ORDER BY start
  `, [userId, startDate, endDate]);

  const workingBlocks = buildWorkingBlocks(
    prefs.rows,
    startDate,
    endDate
  );

  return subtractBusy(workingBlocks, busy.rows);
}

export async function addUserAvailability(
  userId,
  dayOfWeek,
  startTime,
  endTime
) {
  if (dayOfWeek < 0 || dayOfWeek > 6) {
    throw new Error("dayOfWeek must be between 0 and 6");
  }

  if (startTime >= endTime) {
    throw new Error("startTime must be before endTime");
  }

  const result = await db.query(
    `
    INSERT INTO time_slot_preferences
      (user_id, day_of_week, start_time, end_time)
    VALUES ($1, $2, $3, $4)
    RETURNING *
    `,
    [userId, dayOfWeek, startTime, endTime]
  );

  return result.rows[0];
}

